r"""把 SQLite 中的运行数据迁移到 PostgreSQL + pgvector。

示例：

    cd app
    ..\.venv\Scripts\python.exe .\tools\migrate_to_postgres.py --dry-run
    ..\.venv\Scripts\python.exe .\tools\migrate_to_postgres.py `
    --target-url postgresql+psycopg://remotediag:密码@127.0.0.1:5432/remotediag

迁移只做「读 SQLite、写 PostgreSQL」，不会修改或删除 SQLite 原库。
目标库已有数据时默认中止，确认要覆盖再加 `--replace`。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TOOLS_DIR.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine, func, select, text  # noqa: E402

from database import Base  # noqa: E402


DEFAULT_SOURCE = TOOLS_DIR.parent / "data" / "app.db"
BATCH_SIZE = 500
COPY_ORDER_HINT = ("users", "documents", "document_chunks")


def setup_console():
    """让中文输出在 Windows 终端里正常显示。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not reconfigure:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass


def parse_args():
    parser = argparse.ArgumentParser(description="SQLite -> PostgreSQL/pgvector 迁移")
    parser.add_argument(
        "--source",
        default=os.getenv("MIGRATE_SOURCE", str(DEFAULT_SOURCE)),
        help="源 SQLite 文件，默认 app/data/app.db",
    )
    parser.add_argument(
        "--target-url",
        default=os.getenv("POSTGRES_URL", ""),
        help="目标库连接串，默认取环境变量 POSTGRES_URL",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="目标库已有数据时先清空再导入",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只统计要迁移的行数，不写目标库",
    )
    return parser.parse_args()


def require_psycopg():
    try:
        import psycopg  # noqa: F401
    except ImportError:
        print(
            "缺少 PostgreSQL 驱动 psycopg，请先执行：\n"
            "  ..\\.venv\\Scripts\\python.exe -m pip install "
            "-r .\\requirements-postgres.txt",
            file=sys.stderr,
        )
        raise SystemExit(2)


def check_pgvector(connection):
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    found = connection.execute(
        text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
    ).scalar()
    if not found:
        print(
            "目标库没有 pgvector 扩展，请改用带 pgvector 的镜像或先安装扩展。",
            file=sys.stderr,
        )
        raise SystemExit(3)


def source_table_names(connection):
    rows = connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row[0] for row in rows}


def copy_order(tables):
    """按外键依赖排序，并让 documents 相关表排在前面。"""
    ordered = list(Base.metadata.sorted_tables)
    known = {table.name: table for table in ordered}
    head = [known[name] for name in COPY_ORDER_HINT if name in known]
    rest = [table for table in ordered if table.name not in COPY_ORDER_HINT]
    return [table for table in head + rest if table.name in tables]


def reset_sequence(connection, table):
    if "id" not in table.columns:
        return
    connection.execute(
        text(
            f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
            f"COALESCE((SELECT MAX(id) FROM \"{table.name}\"), 0) + 1, false)"
        )
    )


def truncate_all(connection, tables):
    names = ", ".join(f'"{table.name}"' for table in tables)
    connection.execute(text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE"))


def copy_table(source_engine, target_engine, table):
    copied = 0
    with source_engine.connect() as source:
        result = source.execute(select(table))
        while True:
            batch = result.fetchmany(BATCH_SIZE)
            if not batch:
                break
            payload = [dict(row._mapping) for row in batch]
            with target_engine.begin() as target:
                target.execute(table.insert(), payload)
            copied += len(payload)
    return copied


def main():
    setup_console()
    args = parse_args()
    source_path = Path(args.source).expanduser()
    if not source_path.exists():
        print(f"找不到源库：{source_path}", file=sys.stderr)
        return 2
    if not args.target_url:
        print(
            "缺少目标库连接串，请用 --target-url 传入，"
            "或设置环境变量 POSTGRES_URL。",
            file=sys.stderr,
        )
        return 2
    if args.target_url.startswith("sqlite"):
        print("目标库必须是 PostgreSQL 连接串。", file=sys.stderr)
        return 2

    require_psycopg()
    source_engine = create_engine(
        f"sqlite:///{source_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    target_engine = create_engine(args.target_url, future=True)

    try:
        with target_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as error:  # noqa: BLE001
        print(f"无法连接目标库：{error}", file=sys.stderr)
        return 3

    with source_engine.connect() as source:
        tables = copy_order(source_table_names(source))
    if not tables:
        print("源库里没有任何可迁移的业务表。", file=sys.stderr)
        return 2

    counts = {}
    with source_engine.connect() as source:
        for table in tables:
            counts[table.name] = (
                source.execute(select(func.count()).select_from(table)).scalar() or 0
            )

    print(f"源库：{source_path}")
    print(f"目标：{args.target_url.split('@')[-1]}")
    for table in tables:
        print(f"  {table.name:<20} {counts[table.name]:>6} 行")

    if args.dry_run:
        print("dry-run：未写入目标库。")
        source_engine.dispose()
        target_engine.dispose()
        return 0

    with target_engine.begin() as connection:
        check_pgvector(connection)
        Base.metadata.create_all(bind=connection)
        occupied = {}
        for table in tables:
            total = (
                connection.execute(select(func.count()).select_from(table)).scalar()
                or 0
            )
            if total:
                occupied[table.name] = total
        if occupied and not args.replace:
            print(
                "目标库已有数据，未做任何改动："
                + ", ".join(f"{name}={total}" for name, total in occupied.items())
                + "\n确认要覆盖请加 --replace。",
                file=sys.stderr,
            )
            return 4
        if occupied:
            truncate_all(connection, tables)
            print("已清空目标库现有数据。")

    for table in tables:
        copied = copy_table(source_engine, target_engine, table)
        print(f"  {table.name:<20} 已写入 {copied} 行")

    with target_engine.begin() as connection:
        for table in tables:
            reset_sequence(connection, table)
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS chunk_embeddings_vector_idx "
                "ON chunk_embeddings USING hnsw (vector vector_cosine_ops)"
            )
        )
        connection.execute(text("ANALYZE"))

    source_engine.dispose()
    target_engine.dispose()
    print("迁移完成。把 app\\.env 改成：")
    print(f"  DATABASE_URL={args.target_url}")
    print("  VECTOR_BACKEND=pgvector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
