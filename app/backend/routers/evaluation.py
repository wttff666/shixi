from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from deps import require_roles
from services.evaluation import load_cases, run_evaluation


router = APIRouter(
    prefix="/api/admin/evaluation",
    tags=["evaluation"],
    dependencies=[Depends(require_roles("supervisor", "sys_admin"))],
)


@router.get("/cases")
def evaluation_cases():
    return [
        {
            "case_id": case["case_id"],
            "machine_code": case["machine_code"],
            "model": case["model"],
            "symptom": case["symptom"],
            "note": case["note"],
            "expected_fault": case["expected"].get("故障ID", ""),
        }
        for case in load_cases()
    ]


@router.post("/run")
def run_diagnosis_evaluation(limit: int = 5, db: Session = Depends(get_db)):
    if not 1 <= limit <= 10:
        return {"error": "limit 应在 1-10 之间"}
    return run_evaluation(db, limit=limit)
