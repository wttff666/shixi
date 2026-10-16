from __future__ import annotations

import csv
import json
from pathlib import Path

from sqlalchemy.orm import Session

from config import DATA_PACK_DIR
from services.diagnosis import analyze


TEST_SET = DATA_PACK_DIR / "工单_测试集.csv"


def load_cases(path: Path | None = None):
    source = path or TEST_SET
    if not source.exists():
        return []
    with source.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    cases = []
    for row in rows:
        try:
            answer = json.loads(row["标准答案"])
        except (ValueError, KeyError):
            continue
        cases.append(
            {
                "case_id": row["用例编号"],
                "machine_code": row["设备编号"],
                "customer": row["客户"],
                "model": row["机型"],
                "symptom": row["现象描述"],
                "note": row.get("备注", ""),
                "expected": answer,
            }
        )
    return cases


def expected_faults(answer: dict) -> list[str]:
    value = str(answer.get("故障ID", ""))
    if "待确认" in value:
        return []
    return [item for item in value.replace(" ", "").split("/") if item]


def run_evaluation(db: Session, cases=None, limit: int = 5):
    cases = cases if cases is not None else load_cases()
    answerable = 0
    correct = 0
    ambiguous_total = 0
    ambiguous_hedged = 0
    clear_total = 0
    clear_over_ask = 0
    dispatch_expected_no = 0
    dispatch_false = 0
    dispatch_expected_yes = 0
    dispatch_missed = 0
    details = []

    for case in cases:
        result = analyze(
            db,
            case["symptom"],
            machine_code=case["machine_code"],
            limit=limit,
        )
        answer = case["expected"]
        wanted = expected_faults(answer)
        ambiguous = not wanted
        asked = bool(result["follow_up"])
        if ambiguous:
            ambiguous_total += 1
            if asked or result["confidence"] != "high":
                ambiguous_hedged += 1
        else:
            clear_total += 1
            if asked:
                clear_over_ask += 1
            answerable += 1
            if result["fault_id"] in wanted:
                correct += 1
            expected_on_site = answer.get("是否到场", "")
            if expected_on_site == "否":
                dispatch_expected_no += 1
                if result["on_site"] == "是":
                    dispatch_false += 1
            elif expected_on_site == "是":
                dispatch_expected_yes += 1
                if result["on_site"] == "否":
                    dispatch_missed += 1
        details.append(
            {
                "case_id": case["case_id"],
                "machine_code": case["machine_code"],
                "expected_fault": answer.get("故障ID", ""),
                "got_fault": result["fault_id"],
                "confidence": result["confidence"],
                "asked_follow_up": asked,
                "on_site": result["on_site"],
                "correct": (result["fault_id"] in wanted) if wanted else None,
            }
        )

    return {
        "case_count": len(cases),
        "answerable_count": answerable,
        "ambiguous_count": ambiguous_total,
        "diagnosis_accuracy": correct / answerable if answerable else 0.0,
        "follow_up_accuracy": ambiguous_hedged / ambiguous_total
        if ambiguous_total
        else 0.0,
        "over_ask_rate": clear_over_ask / clear_total if clear_total else 0.0,
        "false_dispatch_rate": dispatch_false / dispatch_expected_no
        if dispatch_expected_no
        else 0.0,
        "missed_dispatch_rate": dispatch_missed / dispatch_expected_yes
        if dispatch_expected_yes
        else 0.0,
        "details": details,
    }
