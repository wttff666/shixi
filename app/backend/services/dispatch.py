"""派工建议与对外话术。

内部信息（备件成本、结算、内部通报编号）与对外话术在这里严格分开，
避免把内部信息直接发给客户。
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from models import FaultDefinition, Machine, Ticket


SLA_PATTERN = re.compile(r"(\d+)\s*h\s*响应\s*/\s*(\d+)\s*h\s*到场")


def sla_hours(service_level: str):
    match = SLA_PATTERN.search(service_level or "")
    if not match:
        return 0, 0
    return int(match.group(1)), int(match.group(2))


def historical_eta(db: Session, fault_id: str):
    """同类历史工单的实际耗时，作为工时预估依据。"""
    if not fault_id:
        return "", ""
    rows = db.query(Ticket).filter(Ticket.fault_id == fault_id).all()
    values = []
    for row in rows:
        try:
            values.append(float(row.hours))
        except (TypeError, ValueError):
            continue
    if not values:
        return "", ""
    average = sum(values) / len(values)
    return (
        f"{min(values):.1f}-{max(values):.1f} 小时",
        f"同类历史工单 {len(values)} 条，平均 {average:.1f} 小时",
    )


def build_dispatch(
    db: Session,
    machine: Machine | None,
    fault: FaultDefinition | None,
    confidence: str,
    parts: list[dict],
    bulletin: dict | None,
) -> dict:
    advice = {
        "mode": "",
        "reason": "",
        "sla": "",
        "response_hours": 0,
        "onsite_hours": 0,
        "eta_hours": "",
        "eta_basis": "",
        "second_line": False,
        "second_line_reason": "",
        "parts": parts,
    }
    if machine and machine.warranty:
        advice["sla"] = machine.warranty.service_level
        advice["response_hours"], advice["onsite_hours"] = sla_hours(
            machine.warranty.service_level
        )
    reasons: list[str] = []
    if fault is None:
        advice["mode"] = "待定"
        advice["reason"] = "尚未定位到具体故障，需补充信息后再决定处理方式"
    else:
        on_site = fault.on_site == "是"
        advice["mode"] = "上门处理" if on_site else "远程指导"
        advice["reason"] = fault.reset_method or fault.name
        eta, basis = historical_eta(db, fault.fault_id)
        advice["eta_hours"] = eta
        advice["eta_basis"] = basis
        if on_site and not advice["eta_hours"]:
            advice["eta_hours"] = "待现场评估"
        if fault.severity == "高" and not on_site:
            reasons.append("严重度高的故障，远程指导前建议二线确认")
    if confidence != "high":
        reasons.append("本次为初步判断，建议二线复核后再回复客户")
    if bulletin:
        reasons.append("命中服务通报，处理口径需按通报执行")
    if reasons:
        advice["second_line"] = True
        advice["second_line_reason"] = "；".join(reasons)
    return advice


def build_customer_reply(
    machine: Machine | None,
    symptom: str,
    fault: FaultDefinition | None,
    on_site: str,
    dispatch: dict,
) -> str:
    """可直接发给客户的说明，不含物料号、成本、内部通报编号与责任措辞。"""
    header = "【设备服务初步反馈】"
    lines = [header]
    if machine:
        lines.append(f"设备：{machine.machine_code}（{machine.model_code}）")
        if machine.site_name:
            lines.append(f"位置：{machine.site_name} {machine.line_name}".strip())
    if symptom:
        lines.append(f"您反馈的情况：{symptom.strip()[:120]}")
    if fault:
        lines.append(f"初步判断：{fault.name}" + (f"，依据手册 {fault.manual_section}" if fault.manual_section else ""))
        if fault.reset_method:
            lines.append(f"建议处理：{fault.reset_method}")
    else:
        lines.append("初步判断：目前信息不足，需要进一步确认后再答复")
    mode = dispatch.get("mode") or ""
    if mode == "上门处理":
        lines.append("安排：需要我方工程师到场处理，我们会与您确认时间")
    elif mode == "远程指导":
        lines.append("安排：可通过远程指导处理，稍后我方工程师会与您对接")
    else:
        lines.append("安排：待确认故障后再确定处理方式")
    lines.append("说明：以上为初步判断，最终以现场确认为准。")
    return "\n".join(lines)


def build_internal_notes(
    machine: Machine | None,
    fault: FaultDefinition | None,
    warranty: dict,
    parts: list[dict],
    bulletin: dict | None,
    follow_up: list[str],
) -> list[str]:
    """只对内部可见的备注。"""
    notes: list[str] = []
    if fault and fault.risk:
        notes.append(f"风险：{fault.risk}")
    if warranty:
        notes.append(
            f"结算：{warranty.get('settlement', '')}"
            + (f"（服务等级 {warranty.get('service_level', '')}）" if warranty.get("service_level") else "")
        )
    if parts:
        items = "；".join(
            f"{item['part_no']} {item['name']}（库存 {item['stock']}，货期 {item['lead_days']} 天，参考价 {item['unit_price']} 元）"
            for item in parts
        )
        notes.append(f"建议备件：{items}")
    if bulletin:
        notes.append(
            f"服务通报：{bulletin['bulletin_no']}（有效期至 {bulletin['valid_until']}）"
            f"，{bulletin.get('hint', '')}"
        )
    if follow_up:
        notes.append("待补信息：" + "；".join(follow_up[:3]))
    if machine is None:
        notes.append("未关联设备，结论可能与实际机型不符")
    return notes
