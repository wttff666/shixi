from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from models import Skill


SOURCE_SCOPES = {
    "fault_tree": ("故障树",),
    "bulletin": ("服务通报",),
    "ticket": ("历史工单",),
    "manual": ("手册",),
}


def published_skills(db: Session):
    return (
        db.query(Skill)
        .filter(Skill.status == "published")
        .order_by(Skill.updated_at.desc())
        .all()
    )


def parse_config(skill: Skill | None):
    if not skill:
        return None
    try:
        return json.loads(skill.config_json)
    except ValueError:
        return None


def select_skill(db: Session, question: str, requested_skill_id: str | None = None):
    skills = published_skills(db)
    if not skills:
        return None
    if requested_skill_id:
        return next(
            (skill for skill in skills if skill.skill_id == requested_skill_id), None
        )
    grams = set()
    value = re.sub(r"\s+", "", question or "")
    grams = {value[i:i + 2] for i in range(len(value) - 1)}
    ranked = []
    for skill in skills:
        config = parse_config(skill)
        if not config:
            continue
        body = " ".join(
            [
                skill.name,
                skill.description,
                config.get("instructions", ""),
                " ".join(config.get("retrieval_scope") or []),
            ]
        )
        score = sum(1 for gram in grams if gram in body)
        if score > 0:
            ranked.append((score, skill))
    ranked.sort(key=lambda item: -item[0])
    return ranked[0][1] if ranked else None


def retrieval_allowed(config: dict | None, citations):
    """按 Skill 的 retrieval_scope 过滤引用来源；为空表示不限范围。"""
    if not config:
        return citations
    scope = config.get("retrieval_scope") or []
    if not scope:
        return citations
    prefixes = []
    for item in scope:
        prefixes.extend(SOURCE_SCOPES.get(item, (item,)))
    return [
        item
        for item in citations
        if any(
            prefix in (item.get("source") or "") or prefix in (item.get("ref") or "")
            for prefix in prefixes
        )
    ]


def apply_answer_rule(config: dict | None) -> str:
    if not config:
        return ""
    return (config.get("instructions") or "").strip()[:600]
