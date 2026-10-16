from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from deps import require_roles
from models import AuditLog, DiagnosisRun, ModelCall, ToolCallLog


router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_roles("supervisor", "sys_admin"))],
)


def json_value(value):
    try:
        return json.loads(value or "{}")
    except ValueError:
        return value


@router.get("/diagnosis-runs")
def diagnosis_runs(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    rows = db.query(DiagnosisRun).order_by(DiagnosisRun.id.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "conversation_id": row.conversation_id,
            "machine_code": row.machine_code,
            "fault_id": row.fault_id,
            "fault_name": row.fault_name,
            "confidence": row.confidence,
            "on_site": row.on_site,
            "warranty_status": row.warranty_status,
            "follow_up_count": row.follow_up_count,
            "tool_count": row.tool_count,
            "status": row.status,
            "error": row.error,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
        }
        for row in rows
    ]


@router.get("/model-calls")
def model_calls(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    rows = db.query(ModelCall).order_by(ModelCall.id.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "conversation_id": row.conversation_id,
            "provider": row.provider,
            "model": row.model,
            "status": row.status,
            "input_chars": row.input_chars,
            "output_chars": row.output_chars,
            "elapsed_ms": row.elapsed_ms,
            "error": row.error,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/tool-calls")
def tool_calls(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    rows = db.query(ToolCallLog).order_by(ToolCallLog.id.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "conversation_id": row.conversation_id,
            "diagnosis_run_id": row.diagnosis_run_id,
            "tool_name": row.tool_name,
            "arguments": json_value(row.arguments_json),
            "ok": row.ok,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/audit-logs")
def audit_logs(
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "detail": json_value(row.detail_json),
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)):
    total = db.query(func.count(DiagnosisRun.id)).scalar() or 0
    completed = (
        db.query(func.count(DiagnosisRun.id))
        .filter(DiagnosisRun.status == "completed")
        .scalar()
        or 0
    )
    by_confidence = dict(
        db.query(DiagnosisRun.confidence, func.count(DiagnosisRun.id))
        .group_by(DiagnosisRun.confidence)
        .all()
    )
    follow_up = (
        db.query(func.count(DiagnosisRun.id))
        .filter(DiagnosisRun.follow_up_count > 0)
        .scalar()
        or 0
    )
    on_site_yes = (
        db.query(func.count(DiagnosisRun.id))
        .filter(DiagnosisRun.on_site == "是")
        .scalar()
        or 0
    )
    latency = (
        db.query(func.avg(ModelCall.elapsed_ms))
        .filter(ModelCall.status == "completed")
        .scalar()
    )
    tool_count = db.query(func.count(ToolCallLog.id)).scalar() or 0
    return {
        "diagnosis_total": total,
        "diagnosis_completed": completed,
        "follow_up_rate": (follow_up / total) if total else 0.0,
        "on_site_rate": (on_site_yes / total) if total else 0.0,
        "confidence_distribution": {
            key or "unknown": value for key, value in by_confidence.items()
        },
        "average_model_latency_ms": round(latency or 0.0),
        "tool_call_total": tool_count,
    }
