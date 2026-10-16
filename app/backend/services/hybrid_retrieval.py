from __future__ import annotations

import re

from sqlalchemy.orm import Session

from services.embedding import embed_texts
from services.retrieval import search as lexical_search
from services.vector_store import vector_search


DOMAIN_SIGNAL = re.compile(
    r"料筒|加热|温度|油温|冷却|水温|液压|压力|锁模|合模|开模|"
    r"电机|电流|周期|节拍|螺杆|注塑|射胶|保压|速度|编码器|变频|"
    r"驱动|限位|安全门|干燥|通讯|遥测|报警|故障|停机|异常|振动|"
    r"备件|工单|手册|服务通报|行程|位置"
)


def normalize_scores(items, key):
    if not items:
        return
    maximum = max(float(item.get(key) or 0) for item in items) or 1.0
    for item in items:
        item[key] = float(item.get(key) or 0) / maximum


def search_hybrid(
    db: Session,
    query: str,
    limit: int = 5,
    vector_weight: float = 0.5,
):
    lexical = lexical_search(db, query, limit=max(limit * 2, 5))
    if not lexical and not DOMAIN_SIGNAL.search(query):
        return []
    for item in lexical:
        item["lexical_score"] = item.get("score", 0.0)
        item["vector_score"] = 0.0

    try:
        vectors, _ = embed_texts([query])
        vector_items = vector_search(db, vectors[0], limit=max(limit * 2, 5))
    except Exception:
        return lexical[:limit]

    normalize_scores(lexical, "lexical_score")
    for item in lexical:
        item["score"] = (1 - vector_weight) * item["lexical_score"]
    merged = {}
    for item in lexical:
        merged[item["chunk_id"]] = item
    for item in vector_items:
        existing = merged.get(item["chunk_id"])
        if existing:
            existing["vector_score"] = item["vector_score"]
            existing["score"] = (
                (1 - vector_weight) * existing["lexical_score"]
                + vector_weight * existing["vector_score"]
            )
        else:
            item["lexical_score"] = 0.0
            item["score"] = vector_weight * item["vector_score"]
            merged[item["chunk_id"]] = item

    return sorted(
        merged.values(),
        key=lambda item: item["score"],
        reverse=True,
    )[:limit]
