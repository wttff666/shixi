from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import DocumentChunk


STOPWORDS = {
    "的", "了", "和", "与", "及", "或", "在", "是", "为", "按", "先", "再",
    "后", "进行", "一个", "以及", "相关", "正常", "设备", "问题", "情况",
}

MIN_RELEVANT_SCORE = 5.0


def bigrams(text: str):
    value = re.sub(r"\s+", "", text or "").lower()
    if len(value) < 2:
        return {value} if value else set()
    return {
        value[index:index + 2]
        for index in range(len(value) - 1)
        if value[index:index + 2] not in STOPWORDS
    }


def search(db: Session, query: str, limit: int = 5):
    grams = bigrams(query)
    fault_codes = set(re.findall(r"(?<!\d)\d{5}(?!\d)", query or ""))
    section_refs = set(
        re.findall(r"(?<![\d.])\d+\.\d+(?:\.\d+)?(?![\d.])", query or "")
    )
    chunks = db.scalars(
        select(DocumentChunk).where(DocumentChunk.published.is_(True))
    ).all()
    scored = []
    for chunk in chunks:
        body = f"{chunk.title}\n{chunk.content}\n{chunk.citation}"
        score = sum(1 for gram in grams if gram in body.lower())
        if chunk.section and chunk.section in query:
            score += 4
        if chunk.title and chunk.title in query:
            score += 4
        if fault_codes and any(code in body for code in fault_codes):
            score += 8
        if section_refs and any(ref in body for ref in section_refs):
            score += 5
        if score >= MIN_RELEVANT_SCORE:
            scored.append((score, chunk))
    scored.sort(key=lambda item: (-item[0], item[1].order_index))
    return [
        {
            "chunk_id": chunk.id,
            "ref": chunk.citation,
            "section": chunk.section,
            "title": chunk.title,
            "source": chunk.source_file,
            "text": chunk.content[:1800],
            "score": float(score),
        }
        for score, chunk in scored[:limit]
    ]
