from __future__ import annotations

import json

import httpx

from config import MODEL_API_KEY, MODEL_BASE_URL, MODEL_NAME, MODEL_PROVIDER


ANSWER_MODES = {
    "brief": {
        "citations": 2,
        "snippet_chars": 400,
        "history": 4,
        "max_tokens": 320,
        "rule": (
            "使用简要模式：先给结论，正文不超过 200 字，只列最关键依据，"
            "最多一个小标题，不做背景铺陈。"
        ),
    },
    "standard": {
        "citations": 3,
        "snippet_chars": 800,
        "history": 6,
        "max_tokens": 760,
        "rule": (
            "使用标准模式：先给结论，再给关键依据和下一步建议，"
            "正文 300-500 字，最多三个小节。"
        ),
    },
    "detailed": {
        "citations": 5,
        "snippet_chars": 1400,
        "history": 8,
        "max_tokens": 1200,
        "rule": (
            "使用详细模式：可分小节说明结论、依据、数据、缺失项与下一步，"
            "但仍要避免重复。"
        ),
    },
}


def mode_config(answer_mode):
    return ANSWER_MODES.get(answer_mode, ANSWER_MODES["standard"])


def build_context(citations, diagnosis=None, tool_context="", answer_mode="standard"):
    config = mode_config(answer_mode)
    lines = []
    if diagnosis:
        lines.append("结构化诊断（由系统基于工具与资料给出，请据此组织回答）：")
        lines.append(json.dumps(diagnosis, ensure_ascii=False))
        lines.append("")
    visible = citations[: config["citations"]]
    if not visible:
        lines.append("未检索到可引用资料。")
    else:
        lines.append("检索资料：")
        for index, item in enumerate(visible, start=1):
            lines.append(
                f"[{index}] {item['ref']}\n"
                f"{item['text'][: config['snippet_chars']]}"
            )
    if tool_context:
        lines.extend(["", tool_context[:2600]])
    return "\n".join(lines)


def local_answer(citations, diagnosis=None, answer_mode="standard"):
    """未配置模型时的本地兜底回答。"""
    config = mode_config(answer_mode)
    if diagnosis and diagnosis.get("fault_id"):
        parts = [
            f"疑似故障：{diagnosis['fault_id']} {diagnosis.get('fault_name', '')}",
            f"处置建议：{diagnosis.get('action', '')}",
            f"手册章节：{diagnosis.get('manual_section', '')}",
            f"是否需要到场：{diagnosis.get('on_site', '')}",
        ]
        warranty = diagnosis.get("warranty") or {}
        if warranty:
            parts.append(f"保修判定：{warranty.get('settlement', '')}")
        text = "当前未配置对话模型，先返回结构化诊断结果。\n\n" + "\n".join(parts)
    elif citations:
        text = "当前未配置对话模型，先返回本地检索依据。\n\n" + "\n".join(
            f"[{index}] {item['ref']}\n{item['text'][:240]}"
            for index, item in enumerate(citations[: config["citations"]], start=1)
        )
    else:
        return "当前资料库没有检索到足够依据，请补充设备编号与具体现象。"
    follow_up = (diagnosis or {}).get("follow_up") or []
    if follow_up:
        text += "\n\n需要补充的信息：\n" + "\n".join(
            f"- {item}" for item in follow_up
        )
    return text


def stream_answer(
    question,
    history,
    citations,
    diagnosis=None,
    tool_context="",
    answer_mode="standard",
):
    config = mode_config(answer_mode)
    if not MODEL_API_KEY:
        text = local_answer(citations, diagnosis, answer_mode)
        for start in range(0, len(text), 24):
            yield text[start:start + 24]
        return

    system = (
        "你是注塑机制造商的远程诊断客服助手。只依据提供的检索资料和工具结果回答，"
        f"{config['rule']}"
        "引用资料时使用 [1]、[2] 编号。"
        "优先给出故障 ID、原因、处置要点、手册章节、是否需要到场、涉及备件与保修判定。"
        "资料不足时明确说明缺少哪些信息并给出需要追问的问题，不编造故障、备件或质保规则。"
        "回答使用中文自然语言，不要输出 JSON。"
    )
    messages = [{"role": "system", "content": system}]
    messages.extend(history[-config["history"]:])
    messages.append(
        {
            "role": "user",
            "content": (
                f"{build_context(citations, diagnosis, tool_context, answer_mode)}\n\n"
                f"客户描述：{question}"
            ),
        }
    )
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": True,
        "temperature": 0.2,
        "max_tokens": config["max_tokens"],
    }
    headers = {
        "Authorization": f"Bearer {MODEL_API_KEY}",
        "Content-Type": "application/json",
    }
    url = MODEL_BASE_URL + "/chat/completions"
    try:
        with httpx.stream(
            "POST",
            url,
            headers=headers,
            json=payload,
            timeout=120,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                if line.startswith("data:"):
                    line = line[5:].strip()
                if line == "[DONE]":
                    break
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                choices = event.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                text = delta.get("content")
                if text:
                    yield text
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:300]
        yield f"\n模型调用失败：HTTP {exc.response.status_code} {body}"
    except httpx.HTTPError as exc:
        yield f"\n模型调用失败：{type(exc).__name__}: {exc}"


def provider_info():
    return {"provider": MODEL_PROVIDER, "model": MODEL_NAME, "configured": bool(MODEL_API_KEY)}
