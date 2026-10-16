from __future__ import annotations

from datetime import date, datetime

from config import REFERENCE_DATE


def reference_date() -> date:
    try:
        return datetime.strptime(REFERENCE_DATE, "%Y-%m-%d").date()
    except ValueError:
        return date.today()


def parse_date(value: str) -> date | None:
    for pattern in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime((value or "").strip(), pattern).date()
        except ValueError:
            continue
    return None


def evaluate(warranty, reference: date | None = None) -> dict:
    """判断保修状态与结算方式。

    结算优先级：质保内 > 批次性通报 > 过保收费。批次性通报是否命中由调用方传入，
    在 compose 阶段按服务通报检索结果补全。
    """
    today = reference or reference_date()
    if warranty is None:
        return {
            "status": "未知",
            "settlement": "需人工确认",
            "service_level": "",
            "warranty_end": "",
        }
    end = parse_date(warranty.warranty_end)
    in_warranty = bool(end and end >= today)
    return {
        "status": "保修内" if in_warranty else "已过保",
        "settlement": "保修内免费" if in_warranty else "已过保，需报价",
        "service_level": warranty.service_level,
        "warranty_end": warranty.warranty_end,
    }


def apply_bulletin(decision: dict, bulletin_hit: bool) -> dict:
    """批次性通报命中且已过保时，按通报口径免费。"""
    if bulletin_hit and decision.get("status") == "已过保":
        decision = dict(decision)
        decision["settlement"] = "批次性通报，按通报免费处理"
    return decision
