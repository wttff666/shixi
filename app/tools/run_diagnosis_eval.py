"""运行诊断评测：对内置评测用例跑一遍完整诊断链路，输出指标与明细。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = APP_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal, init_db  # noqa: E402
from services.evaluation import load_cases, run_evaluation  # noqa: E402
from services.seed import seed_all  # noqa: E402


SUMMARY_KEYS = (
    "case_count",
    "answerable_count",
    "ambiguous_count",
    "diagnosis_accuracy",
    "follow_up_accuracy",
    "over_ask_rate",
    "false_dispatch_rate",
    "missed_dispatch_rate",
)


def main():
    parser = argparse.ArgumentParser(description="Run remote diagnosis evaluation")
    parser.add_argument("--limit", type=int, default=5, help="每条用例检索条数")
    parser.add_argument(
        "--output",
        type=Path,
        default=APP_DIR / "data" / "diagnosis-eval.json",
    )
    args = parser.parse_args()

    init_db()
    seed_all()
    db = SessionLocal()
    try:
        result = run_evaluation(db, load_cases(), limit=args.limit)
    finally:
        db.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {key: result[key] for key in SUMMARY_KEYS},
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"result_file={args.output}")


if __name__ == "__main__":
    main()
