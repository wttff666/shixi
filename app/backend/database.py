from __future__ import annotations

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import DATABASE_URL, VECTOR_BACKEND


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_sqlite_schema(bind=None):
    """SQLite 旧库的最小兼容处理。

    早期版本把向量存在 `chunk_embeddings.vector_json`，现在统一叫 `vector`。
    只做列重命名，不动数据。
    """
    engine_ = bind or engine
    if engine_.dialect.name != "sqlite":
        return
    inspector = inspect(engine_)
    if "chunk_embeddings" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("chunk_embeddings")}
    if "vector_json" in columns and "vector" not in columns:
        with engine_.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE chunk_embeddings RENAME COLUMN vector_json TO vector"
            )


def ensure_pgvector_extension(bind=None):
    """PostgreSQL 后端下确认 pgvector 扩展可用。"""
    engine_ = bind or engine
    if engine_.dialect.name != "postgresql" or VECTOR_BACKEND != "pgvector":
        return False
    try:
        with engine_.begin() as connection:
            connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception as error:  # noqa: BLE001
        raise RuntimeError(
            "无法启用 pgvector 扩展，请确认目标库是 pgvector 镜像，"
            f"或让数据库管理员执行 CREATE EXTENSION vector。原始错误：{error}"
        ) from error
    return True


def init_db():
    import models  # noqa: F401

    ensure_pgvector_extension()
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema()
