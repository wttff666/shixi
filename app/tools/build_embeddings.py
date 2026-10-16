from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = APP_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal, init_db  # noqa: E402
from services.vector_store import rebuild_embeddings  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Build local BGE-M3 embeddings")
    parser.add_argument("--model", default="BAAI/bge-m3")
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        result = rebuild_embeddings(
            db,
            model_name=args.model,
            batch_size=args.batch_size,
        )
    finally:
        db.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
