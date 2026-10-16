from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from models import FaultDefinition, Machine, SparePart, Ticket
from services import warranty as warranty_service
from services.dispatch import (
    build_customer_reply,
    build_dispatch,
    build_internal_notes,
)
from services.mcp_gateway import MCPGateway


# 现场描述里的关键词到测点的映射，用于按现象拉取相关遥测。
PARAM_HINTS = {
    "温度": ["T_BARREL1", "T_BARREL2", "T_BARREL3", "T_OIL", "T_MOTOR", "T_MOLD"],
    "料筒": ["T_BARREL1", "T_BARREL2", "T_BARREL3", "T_SET1"],
    "油温": ["T_OIL", "T_COOL_IN", "F_COOL"],
    "冷却": ["F_COOL", "T_COOL_IN", "T_OIL"],
    "水温": ["T_COOL_IN", "F_COOL"],
    "压力": ["P_HYD", "P_INJ", "P_HOLD"],
    "锁模": ["P_HYD", "F_CLAMP", "V_CLAMP"],
    "电机": ["C_MOTOR", "T_MOTOR"],
    "电流": ["C_MOTOR"],
    "周期": ["CYCLE_TIME", "T_INJ"],
    "节拍": ["CYCLE_TIME"],
    "螺杆": ["T_INJ", "P_INJ"],
    "注塑": ["T_INJ", "P_INJ", "V_INJ"],
    "速度": ["V_INJ", "V_CLAMP"],
    "编码器": ["V_INJ", "V_CLAMP", "POS_ERR"],
    "锁模力": ["F_CLAMP", "V_CLAMP"],
}

DEFAULT_PARAMS = ["T_OIL", "C_MOTOR", "P_HYD", "F_COOL", "CYCLE_TIME"]


def params_for(question: str, fault: FaultDefinition | None) -> list[str]:
    names: list[str] = []
    if fault:
        names.extend(re.findall(r"[A-Z][A-Z_0-9]{2,}", fault.key_params or ""))
    for keyword, params in PARAM_HINTS.items():
        if keyword in (question or ""):
            names.extend(params)
    if not names:
        names = list(DEFAULT_PARAMS)
    return list(dict.fromkeys(names))[:8]


def resolve_machine(db: Session, question: str, machine_code: str | None):
    code = (machine_code or "").strip().upper()
    if not code:
        match = re.search(r"\bM0*(\d{1,3})\b", question or "", re.IGNORECASE)
        if match:
            code = f"M{int(match.group(1)):03d}"
    if not code:
        match = re.search(r"(IMP\d{3}T\d{6})", question or "", re.IGNORECASE)
        if match:
            machine = (
                db.query(Machine)
                .filter(Machine.serial_no == match.group(1).upper())
                .first()
            )
            if machine:
                return machine
    if not code:
        match = re.search(r"ZJ-\d{4}-\d{4}", question or "", re.IGNORECASE)
        if match:
            ticket = (
                db.query(Ticket)
                .filter(Ticket.ticket_no == match.group(0).upper())
                .first()
            )
            if ticket:
                code = ticket.machine_code
    if not code:
        return None
    return db.query(Machine).filter(Machine.machine_code == code).first()


def fault_by_id(db: Session, fault_id: str) -> FaultDefinition | None:
    if not fault_id:
        return None
    return (
        db.query(FaultDefinition)
        .filter(FaultDefinition.fault_id == fault_id)
        .first()
    )


def _grams(text: str) -> set[str]:
    value = re.sub(r"\s+", "", text or "").lower()
    if len(value) < 2:
        return {value} if value else set()
    return {value[index:index + 2] for index in range(len(value) - 1)}


def name_in_question(name: str, question: str) -> bool:
    """故障名称中有 3 字以上的片段出现在问题里，视为名称命中。"""
    clean_name = re.sub(r"\s+", "", name or "")
    clean_question = re.sub(r"\s+", "", question or "")
    if len(clean_name) < 3 or len(clean_question) < 3:
        return False
    return any(
        clean_name[index:index + 3] in clean_question
        for index in range(len(clean_name) - 2)
    )


def select_fault(db: Session, question: str, citations, tool_data: dict):
    """综合文本匹配、检索命中的章节与相似工单，选出最可能的故障。"""
    grams = _grams(question)
    faults = {row.fault_id: row for row in db.query(FaultDefinition).all()}
    if not faults:
        return None
    scores: dict[str, float] = {}
    for fault_id, fault in faults.items():
        body = " ".join(
            [
                fault.name,
                fault.group_name,
                fault.alarm_condition,
                fault.key_params,
                fault.keywords,
            ]
        ).lower()
        scores[fault_id] = float(sum(1 for gram in grams if gram in body))
        if name_in_question(fault.name, question):
            scores[fault_id] += 5.0
    for item in citations or []:
        section = (item.get("section") or "").strip()
        if not section:
            continue
        for fault_id, fault in faults.items():
            if fault.manual_section and fault.manual_section == section:
                scores[fault_id] += 3.0
    tickets = (tool_data.get("tickets_search") or {}).get("tickets") or []
    for rank, ticket in enumerate(tickets[:3]):
        fault_id = ticket.get("fault_id")
        if fault_id in scores:
            scores[fault_id] += 4.0 - rank
    best_id = max(scores, key=lambda key: scores[key])
    if scores[best_id] < 4.0:
        return None
    return faults[best_id]


def fault_from_citations(db: Session, citations) -> FaultDefinition | None:
    for item in citations or []:
        section = (item.get("section") or "").strip()
        if not section:
            continue
        fault = (
            db.query(FaultDefinition)
            .filter(FaultDefinition.manual_section == section)
            .first()
        )
        if fault:
            return fault
    return None


def run_tools(
    db: Session, machine: Machine | None, question: str, citations=None
):
    """按需调用只读 MCP 工具，返回调用日志、结果集合与命中的故障定义。"""
    logs: list[dict] = []
    data: dict[str, dict] = {}

    def call(gateway, name, arguments):
        result = gateway.call(name, arguments)
        logs.append(
            {
                "name": name,
                "arguments": arguments,
                "ok": bool(result.get("ok")),
                "data": result.get("data") if result.get("ok") else result.get("error"),
            }
        )
        if result.get("ok"):
            data[name] = result["data"]
        return result

    try:
        with MCPGateway() as gateway:
            call(gateway, "fault_tree_lookup", {"query": question[:200], "limit": 3})
            call(gateway, "tickets_search", {"query": question[:200], "limit": 3})
            fault = select_fault(db, question, citations, data)

            if machine:
                call(
                    gateway,
                    "device_profile",
                    {"machine_code": machine.machine_code},
                )
                call(
                    gateway,
                    "warranty_lookup",
                    {"machine_code": machine.machine_code},
                )
                call(
                    gateway,
                    "device_active_faults",
                    {"machine_code": machine.machine_code},
                )
                call(
                    gateway,
                    "device_latest",
                    {"machine_code": machine.machine_code},
                )

            if fault and fault.part_no:
                call(gateway, "spare_part_lookup", {"part_no": fault.part_no})
            elif machine:
                call(
                    gateway,
                    "spare_part_lookup",
                    {"model": machine.model_code},
                )
            else:
                call(
                    gateway,
                    "spare_part_lookup",
                    {"keyword": question[:40]},
                )

            call(
                gateway,
                "service_bulletin_lookup",
                {
                    "model": machine.model_code if machine else "",
                    "keyword": question[:80],
                },
            )

            if machine:
                call(
                    gateway,
                    "device_telemetry",
                    {
                        "machine_code": machine.machine_code,
                        "params": params_for(question, fault),
                    },
                )
    except Exception as exc:  # noqa: BLE001
        logs.append(
            {
                "name": "mcp_gateway",
                "arguments": {},
                "ok": False,
                "data": f"{type(exc).__name__}: {exc}",
            }
        )
    return logs, data, fault


def corroborated(fault: FaultDefinition | None, tool_data: dict) -> bool:
    if not fault:
        return False
    active = (tool_data.get("device_active_faults") or {}).get("faults") or []
    tokens = set(re.findall(r"[A-Z][A-Z_0-9]{2,}", fault.key_params or ""))
    for item in active:
        if item.get("param") in tokens:
            return True
        name = item.get("name") or ""
        if fault.name and name and (fault.name[:2] in name or name[:2] in fault.name):
            return True
    return False


def hazard_parts(db: Session, fault: FaultDefinition | None) -> list[dict]:
    if not fault or not fault.part_no:
        return []
    part = db.query(SparePart).filter(SparePart.part_no == fault.part_no).first()
    if not part:
        return []
    return [
        {
            "part_no": part.part_no,
            "name": part.name,
            "spec": part.spec,
            "stock": part.stock,
            "lead_days": part.lead_days,
            "unit_price": part.unit_price,
        }
    ]


def best_bulletin(tool_data: dict) -> dict | None:
    bulletins = (
        (tool_data.get("service_bulletin_lookup") or {}).get("bulletins") or []
    )
    return bulletins[0] if bulletins else None


def compose(
    db: Session,
    question: str,
    machine: Machine | None,
    fault: FaultDefinition | None,
    citations,
    tool_data: dict,
) -> dict:
    if fault is None:
        fault = fault_from_citations(db, citations)

    if fault and (corroborated(fault, tool_data) or name_in_question(fault.name, question)):
        confidence = "high"
    elif fault:
        confidence = "medium"
    else:
        confidence = "undetermined"

    decision = warranty_service.evaluate(machine.warranty if machine else None)
    bulletin = best_bulletin(tool_data)
    decision = warranty_service.apply_bulletin(decision, bool(bulletin))

    summary = (tool_data.get("device_latest") or {}).get("values") or {}
    key_params = re.findall(r"[A-Z][A-Z_0-9]{2,}", fault.key_params or "") if fault else []
    observations = {
        name: summary[name] for name in key_params if name in summary
    }

    follow_up: list[str] = []
    missing: list[str] = []
    if machine is None:
        follow_up.append(
            "请提供设备编号（如 M001）或出厂编号，便于定位设备档案与保修信息。"
        )
        missing.append("设备编号")
    if fault is None:
        follow_up.append("请描述报警画面或报警编号，以及具体的异常现象。")
        missing.append("报警信息")
    elif confidence != "high":
        for item in json.loads(fault.questions_json or "[]")[:3]:
            follow_up.append(item)
        missing.append("关键区分信息")

    tickets = (tool_data.get("tickets_search") or {}).get("tickets") or []
    parts = hazard_parts(db, fault)
    dispatch = build_dispatch(db, machine, fault, confidence, parts, bulletin)
    customer_reply = build_customer_reply(
        machine, question, fault, fault.on_site if fault else "", dispatch
    )
    internal_notes = build_internal_notes(
        machine, fault, decision, parts, bulletin, follow_up
    )

    return {
        "machine_code": machine.machine_code if machine else "",
        "model_code": machine.model_code if machine else "",
        "customer_name": machine.customer_name if machine else "",
        "service_request_no": "",
        "fault_id": fault.fault_id if fault else "",
        "fault_name": fault.name if fault else "",
        "severity": fault.severity if fault else "",
        "manual_section": fault.manual_section if fault else "",
        "cause": fault.cause if fault else "",
        "action": fault.reset_method if fault else "",
        "risk": fault.risk if fault else "",
        "on_site": fault.on_site if fault else "",
        "confidence": confidence,
        "observations": observations,
        "parts": parts,
        "warranty": decision,
        "bulletin": (
            {
                "bulletin_no": bulletin["bulletin_no"],
                "hint": bulletin["hint"],
                "action": bulletin["action"],
                "valid_until": bulletin["valid_until"],
            }
            if bulletin
            else None
        ),
        "dispatch": dispatch,
        "follow_up": follow_up,
        "missing": missing,
        "internal_notes": internal_notes,
        "customer_reply": customer_reply,
        "citations": citations,
        "similar_tickets": tickets[:3],
    }


def tool_context_text(logs) -> str:
    lines = ["MCP 工具结果："]
    for item in logs:
        if not item.get("ok"):
            lines.append(f"- {item['name']}: 调用失败（{item.get('data')}）")
            continue
        payload = json.dumps(item["data"], ensure_ascii=False)
        lines.append(f"- {item['name']}: {payload[:1200]}")
    return "\n".join(lines)


def analyze(
    db: Session,
    question: str,
    machine: Machine | None = None,
    machine_code: str | None = None,
    limit: int = 5,
):
    """非流式诊断，供评测与批量脚本复用。"""
    from services.retrieval_facade import retrieve

    if machine is None:
        machine = resolve_machine(db, question, machine_code)
    citations = retrieve(db, question, limit=limit)
    tools, tool_data, fault = run_tools(db, machine, question, citations)
    result = compose(db, question, machine, fault, citations, tool_data)
    result["_tools"] = [item["name"] for item in tools if item.get("ok")]
    return result
