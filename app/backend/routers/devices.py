from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from deps import get_current_user
from models import Customer, FaultDefinition, Machine, MachineModel, SparePart, ServiceBulletin, Ticket
from schemas import (
    CustomerOut,
    FaultDefinitionOut,
    MachineModelOut,
    MachineOut,
    ServiceBulletinOut,
    SparePartOut,
    TicketOut,
)
from services import warranty as warranty_service
from services.mcp_gateway import MCPGateway


router = APIRouter(prefix="/api", tags=["devices"])


def scoped_query(query, user, model=Machine):
    if user.role == "customer":
        query = query.filter(model.customer_name == user.customer_name)
    return query


def machine_view(machine: Machine) -> dict:
    decision = warranty_service.evaluate(machine.warranty)
    return {
        "id": machine.id,
        "machine_code": machine.machine_code,
        "model_code": machine.model_code,
        "model_name": machine.model_name,
        "serial_no": machine.serial_no,
        "customer_name": machine.customer_name,
        "site_name": machine.site_name,
        "line_name": machine.line_name,
        "production_date": machine.production_date,
        "install_date": machine.install_date,
        "status": machine.status,
        "firmware": machine.firmware,
        "last_service_at": machine.last_service_at,
        "warranty_status": decision["status"],
        "warranty_end": decision["warranty_end"],
    }


def get_machine(db: Session, machine_code: str, user) -> Machine:
    machine = (
        db.query(Machine)
        .filter(Machine.machine_code == machine_code.strip().upper())
        .first()
    )
    if not machine:
        raise HTTPException(status_code=404, detail="设备不存在")
    if user.role == "customer" and machine.customer_name != user.customer_name:
        raise HTTPException(status_code=404, detail="设备不存在")
    return machine


@router.get("/customers", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db), user=Depends(get_current_user)):
    query = db.query(Customer).order_by(Customer.name)
    if user.role == "customer":
        query = query.filter(Customer.name == user.customer_name)
    return query.all()


@router.get("/machine-models", response_model=list[MachineModelOut])
def list_machine_models(
    db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return db.query(MachineModel).order_by(MachineModel.code).all()


@router.get("/machines", response_model=list[MachineOut])
def list_machines(
    customer: str | None = None,
    model: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = scoped_query(db.query(Machine), user)
    if customer:
        query = query.filter(Machine.customer_name == customer)
    if model:
        query = query.filter(Machine.model_code == model)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            Machine.machine_code.like(like)
            | Machine.serial_no.like(like)
            | Machine.model_code.like(like)
        )
    return [machine_view(item) for item in query.order_by(Machine.machine_code).all()]


@router.get("/machines/{machine_code}", response_model=MachineOut)
def machine_detail(
    machine_code: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return machine_view(get_machine(db, machine_code, user))


def call_tool(name: str, arguments: dict):
    with MCPGateway() as gateway:
        result = gateway.call(name, arguments)
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("error") or "工具调用失败")
    return result["data"]


@router.get("/machines/{machine_code}/latest")
def machine_latest(
    machine_code: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    machine = get_machine(db, machine_code, user)
    return call_tool("device_latest", {"machine_code": machine.machine_code})


@router.get("/machines/{machine_code}/telemetry")
def machine_telemetry(
    machine_code: str,
    params: str | None = None,
    start: str | None = None,
    end: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    machine = get_machine(db, machine_code, user)
    arguments = {"machine_code": machine.machine_code}
    if params:
        arguments["params"] = [item.strip() for item in params.split(",") if item.strip()]
    if start:
        arguments["start"] = start
    if end:
        arguments["end"] = end
    return call_tool("device_telemetry", arguments)


@router.get("/machines/{machine_code}/alarms")
def machine_alarms(
    machine_code: str,
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    machine = get_machine(db, machine_code, user)
    return call_tool(
        "alarm_history", {"machine_code": machine.machine_code, "limit": limit}
    )


@router.get("/faults", response_model=list[FaultDefinitionOut])
def list_faults(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(FaultDefinition).order_by(FaultDefinition.manual_section).all()
    return [
        {
            "fault_id": row.fault_id,
            "code": row.code,
            "name": row.name,
            "group_name": row.group_name,
            "severity": row.severity,
            "alarm_condition": row.alarm_condition,
            "key_params": row.key_params,
            "manual_section": row.manual_section,
            "reset_method": row.reset_method,
            "part_no": row.part_no,
            "on_site": row.on_site,
            "questions": [],
            "steps": [],
        }
        for row in rows
    ]


@router.get("/spare-parts", response_model=list[SparePartOut])
def list_spare_parts(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(SparePart).order_by(SparePart.part_no).all()


@router.get("/service-bulletins", response_model=list[ServiceBulletinOut])
def list_service_bulletins(
    db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return db.query(ServiceBulletin).order_by(ServiceBulletin.bulletin_no).all()


@router.get("/tickets", response_model=list[TicketOut])
def list_tickets(
    machine_code: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = db.query(Ticket)
    if user.role == "customer":
        query = query.filter(Ticket.customer_name == user.customer_name)
    if machine_code:
        query = query.filter(Ticket.machine_code == machine_code.strip().upper())
    rows = query.order_by(Ticket.reported_at.desc()).limit(limit).all()
    return rows
