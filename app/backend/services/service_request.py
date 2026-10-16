from __future__ import annotations

import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import Machine, ServiceRequest


REQUEST_STATUSES = ("待研判", "待派工", "已派工", "已研判", "已关闭")


def next_request_no(db: Session) -> str:
    year = datetime.now().year
    prefix = f"SR-{year}-"
    latest = (
        db.query(ServiceRequest)
        .filter(ServiceRequest.request_no.like(f"{prefix}%"))
        .order_by(ServiceRequest.request_no.desc())
        .first()
    )
    sequence = 1
    if latest:
        try:
            sequence = int(latest.request_no.rsplit("-", 1)[1]) + 1
        except (IndexError, ValueError):
            sequence = db.query(ServiceRequest).count() + 1
    return f"{prefix}{sequence:04d}"


def create_request(
    db: Session,
    *,
    customer_name: str,
    machine_code: str,
    symptom: str,
    channel: str = "电话",
    priority: str = "普通",
    handler=None,
) -> ServiceRequest:
    machine = (
        db.query(Machine)
        .filter(Machine.machine_code == machine_code.strip().upper())
        .first()
    )
    if not machine:
        raise HTTPException(status_code=404, detail="设备不存在")
    if customer_name and machine.customer_name != customer_name:
        raise HTTPException(status_code=400, detail="设备与客户不匹配")
    request = ServiceRequest(
        request_no=next_request_no(db),
        customer_name=machine.customer_name,
        machine_code=machine.machine_code,
        model_code=machine.model_code,
        channel=channel,
        priority=priority,
        status="待研判",
        symptom=symptom.strip(),
        handler_id=getattr(handler, "id", None),
        handler_name=getattr(handler, "username", ""),
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def scoped(query, user):
    """客户方账号只能看自己企业的工单。"""
    if getattr(user, "role", "") == "customer":
        return query.filter(ServiceRequest.customer_name == user.customer_name)
    return query


def get_request(db: Session, request_id: int, user) -> ServiceRequest:
    request = db.get(ServiceRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="工单不存在")
    if getattr(user, "role", "") == "customer" and request.customer_name != user.customer_name:
        raise HTTPException(status_code=404, detail="工单不存在")
    return request


def apply_diagnosis(
    request: ServiceRequest,
    diagnosis: dict,
    run_id: int | None,
    conversation_id: int | None,
) -> None:
    """把诊断结论写回工单，并推进状态。"""
    request.fault_id = diagnosis.get("fault_id", "")
    request.fault_name = diagnosis.get("fault_name", "")
    request.confidence = diagnosis.get("confidence", "")
    request.on_site = diagnosis.get("on_site", "")
    request.dispatch_json = json.dumps(diagnosis.get("dispatch") or {}, ensure_ascii=False)
    request.customer_reply = diagnosis.get("customer_reply", "")
    request.internal_notes_json = json.dumps(
        diagnosis.get("internal_notes") or [], ensure_ascii=False
    )
    if run_id:
        request.diagnosis_run_id = run_id
    if conversation_id:
        request.conversation_id = conversation_id
    if request.status == "待研判":
        request.status = "待派工" if diagnosis.get("on_site") == "是" else "已研判"


def detail(db: Session, request: ServiceRequest) -> dict:
    try:
        dispatch = json.loads(request.dispatch_json or "{}")
    except ValueError:
        dispatch = {}
    try:
        notes = json.loads(request.internal_notes_json or "[]")
    except ValueError:
        notes = []
    run = None
    if request.diagnosis_run_id:
        from models import DiagnosisRun

        run = db.get(DiagnosisRun, request.diagnosis_run_id)
    citations = []
    similar = []
    if run and run.diagnosis_json:
        try:
            stored = json.loads(run.diagnosis_json)
        except ValueError:
            stored = {}
        citations = stored.get("citations") or []
        similar = stored.get("similar_tickets") or []
    return {
        "id": request.id,
        "request_no": request.request_no,
        "customer_name": request.customer_name,
        "machine_code": request.machine_code,
        "model_code": request.model_code,
        "channel": request.channel,
        "priority": request.priority,
        "status": request.status,
        "symptom": request.symptom,
        "handler_name": request.handler_name,
        "fault_id": request.fault_id,
        "fault_name": request.fault_name,
        "confidence": request.confidence,
        "on_site": request.on_site,
        "created_at": request.created_at,
        "updated_at": request.updated_at,
        "dispatch": dispatch,
        "customer_reply": request.customer_reply,
        "internal_notes": notes,
        "closed_note": request.closed_note,
        "conversation_id": request.conversation_id,
        "citations": citations,
        "similar_tickets": similar,
    }
