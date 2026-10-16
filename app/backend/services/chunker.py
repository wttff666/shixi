from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from services.parser import ParsedBlock


STRATEGIES = {
    "punctuation": "按标点切片",
    "paragraph": "按段落切片",
    "heading": "按标题切片",
    "fixed": "按固定长度切片",
}


@dataclass
class ChunkDraft:
    order_index: int
    section: str
    title: str
    content: str
    page_start: int
    page_end: int
    citation: str
    strategy: str
    content_hash: str


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def merge_parts(parts, max_chars, overlap_chars):
    chunks = []
    current = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if current and len(current) + len(part) + 1 > max_chars:
            chunks.append(current.strip())
            tail = current[-overlap_chars:] if overlap_chars else ""
            current = (tail + "\n" + part).strip()
        else:
            current = (current + "\n" + part).strip() if current else part
    if current.strip():
        chunks.append(current.strip())
    return chunks


def split_punctuation(text, max_chars, overlap_chars):
    parts = re.split(r"(?<=[。！？；!?;])", text)
    return merge_parts(parts, max_chars, overlap_chars)


def split_paragraphs(text, max_chars, overlap_chars):
    parts = re.split(r"\n\s*\n+", text)
    return merge_parts(parts, max_chars, overlap_chars)


def split_fixed(text, max_chars, overlap_chars):
    text = text.strip()
    chunks = []
    step = max(1, max_chars - overlap_chars)
    for start in range(0, len(text), step):
        part = text[start:start + max_chars].strip()
        if part:
            chunks.append(part)
        if start + max_chars >= len(text):
            break
    return chunks


def split_headings(text, max_chars, overlap_chars):
    pattern = re.compile(
        r"^(?:#{1,6}\s+|\d+(?:\.\d+){0,2}\s+|[一二三四五六七八九十]+、)",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(text))
    if not matches:
        return split_paragraphs(text, max_chars, overlap_chars)
    sections = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[start:end].strip()
        if section:
            sections.append(section)
    return merge_parts(sections, max_chars, overlap_chars)


def detect_heading(text: str):
    first_line = (text or "").splitlines()[0].strip()
    match = re.match(r"^(?:#{1,6}\s+|(\d+(?:\.\d+){0,2})\s+)(.+)$", first_line)
    if not match:
        return "", first_line[:80]
    return match.group(1) or "", (match.group(2) or "").strip()


def chunk_blocks(
    blocks: list[ParsedBlock],
    source_file: str,
    strategy: str = "punctuation",
    max_chars: int = 800,
    overlap_chars: int = 100,
) -> list[ChunkDraft]:
    if strategy not in STRATEGIES:
        raise ValueError(f"未知切片策略：{strategy}")
    if max_chars < 100:
        raise ValueError("max_chars 不能小于 100")
    overlap_chars = max(0, min(overlap_chars, max_chars // 2))

    drafts = []
    order = 0
    for block in blocks:
        if strategy == "punctuation":
            parts = split_punctuation(block.text, max_chars, overlap_chars)
        elif strategy == "paragraph":
            parts = split_paragraphs(block.text, max_chars, overlap_chars)
        elif strategy == "heading":
            parts = split_headings(block.text, max_chars, overlap_chars)
        else:
            parts = split_fixed(block.text, max_chars, overlap_chars)

        for part in parts:
            order += 1
            section, title = detect_heading(part)
            citation = (
                f"{source_file} · {section + ' ' if section else ''}"
                f"{title} · 第{block.page}页"
            )
            drafts.append(
                ChunkDraft(
                    order_index=order,
                    section=section,
                    title=title,
                    content=part,
                    page_start=block.page,
                    page_end=block.page,
                    citation=citation,
                    strategy=strategy,
                    content_hash=content_hash(part),
                )
            )
    return drafts
