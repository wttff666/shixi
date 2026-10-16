from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from deps import get_current_user, require_roles
from models import ServiceRequest
from schemas import (
    ServiceRequestCreate,
    ServiceRequestDetail,
    ServiceRequestOut,
    ServiceRequestUpdate,
)
from services.audit import record_audit
from services.service_request import (
    REQUEST_STATUSES,
    create_request,
    detail,
    get_request,
    scoped,
)


router = APIRouter(prefix="/api", tags=["service-requests"])

internal_only = require_roles("agent", "tech", "supervisor", "sys_admin")


@router.get("/service-requests/options")
def request_options(user=Depends(get_current_user)):
    return {
        "status": list(REQUEST_STATUSES),
        "channel": ["电话", "平台", "邮件", "现场"],
        "priority": ["紧急", "高", "普通"],
    }


@router.get("/service-requests", response_model=list[ServiceRequestOut])
def list_requests(
    status: str | None = None,
    customer: str | None = None,
    machine_code: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = scoped(db.query(ServiceRequest), user)
    if status:
        query = query.filter(ServiceRequest.status == status)
    if customer:
        query = query.filter(ServiceRequest.customer_name == customer)
    if machine_code:
        query = query.filter(
            ServiceRequest.machine_code == machine_code.strip().upper()
        )
    return query.order_by(ServiceRequest.id.desc()).limit(limit).all()


@router.post("/service-requests", response_model=ServiceRequestDetail)
def create(
    request: ServiceRequestCreate,
    db: Session = Depends(get_db),
    user=Depends(internal_only),
):
    service_request = create_request(
        db,
        customer_name=request.customer_name,
        machine_code=request.machine_code,
        symptom=request.symptom,
        channel=request.channel,
        priority=request.priority,
        handler=user,
    )
    record_audit(
        db,
        user_id=user.id,
        action="service_request.create",
        entity_type="service_request",
        entity_id=service_request.request_no,
        detail={
            "machine_code": service_request.machine_code,
            "priority": service_request.priority,
        },
    )
    return detail(db, service_request)


@router.get("/service-requests/{request_id}", response_model=ServiceRequestDetail)
def request_detail(
    request_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return detail(db, get_request(db, request_id, user))


@router.patch("/service-requests/{request_id}", response_model=ServiceRequestDetail)
def update_request(
    request_id: int,
    payload: ServiceRequestUpdate,
    db: Session = Depends(get_db),
    user=Depends(internal_only),
):
    service_request = get_request(db, request_id, user)
    if payload.status:
        if payload.status not in REQUEST_STATUSES:
            raise HTTPException(status_code=400, detail="未知工单状态")
        service_request.status = payload.status
    if payload.priority:
        service_request.priority = payload.priority
    if payload.channel:
        service_request.channel = payload.channel
    if payload.handler_name is not None:
        service_request.handler_name = payload.handler_name.strip()
    if payload.closed_note is not None:
        service_request.closed_note = payload.closed_note.strip()
    db.commit()
    db.refresh(service_request)
    record_audit(
        db,
        user_id=user.id,
        action="service_request.update",
        entity_type="service_request",
        entity_id=service_request.request_no,
        detail={"status": service_request.status, "priority": service_request.priority},
    )
    return detail(db, service_request)
