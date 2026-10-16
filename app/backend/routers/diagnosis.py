from __future__ import annotations

import json
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from config import MODEL_NAME, MODEL_PROVIDER
from database import SessionLocal, get_db
from deps import get_current_user
from models import DiagnosisRun, Machine, Message, ModelCall, ServiceRequest, ToolCallLog
from schemas import DiagnosisRequest
from services.conversation import (
    append_message,
    create_conversation,
    get_owned_conversation,
)
from services.diagnosis import compose, resolve_machine, run_tools, tool_context_text
from services.model_gateway import stream_answer
from services.retrieval_facade import retrieve
from services.service_request import apply_diagnosis, get_request
from services.skill_runtime import (
    parse_config,
    retrieval_allowed,
    select_skill,
)


router = APIRouter(prefix="/api", tags=["diagnosis"])


def event(payload):
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


def require_internal(user):
    """诊断是内部客服能力；客户账号只能查询服务记录。"""
    if user.role == "customer":
        raise HTTPException(
            status_code=403,
            detail="客户账号仅可查询本企业设备与服务记录，不能发起内部诊断",
        )


@router.post("/diagnosis")
def diagnosis(
    request: DiagnosisRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_internal(user)
    if request.conversation_id:
        conversation = get_owned_conversation(db, request.conversation_id, user.id)
    else:
        conversation = create_conversation(db, user.id, "新诊断")
    append_message(db, conversation.id, "user", request.message)
    if conversation.title == "新诊断":
        conversation.title = request.message.strip()[:30] or "新诊断"
        db.commit()

    service_request = None
    if request.service_request_id:
        service_request = get_request(db, request.service_request_id, user)

    machine = resolve_machine(db, request.message, request.machine_code)
    if machine is None and service_request:
        machine = (
            db.query(Machine)
            .filter(Machine.machine_code == service_request.machine_code)
            .first()
        )
    skill = select_skill(db, request.message, request.skill_id)
    skill_config = parse_config(skill)
    citations = retrieval_allowed(
        skill_config, retrieve(db, request.message, limit=5)
    )
    history_rows = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.id)
        .all()
    )
    history = [
        {"role": item.role, "content": item.content[:4000]}
        for item in history_rows[:-1][-8:]
        if item.role in ("user", "assistant")
    ]

    def generate():
        stream_db = SessionLocal()
        run = None
        model_call = None
        answer_parts: list[str] = []
        try:
            run = DiagnosisRun(
                conversation_id=conversation.id,
                user_id=user.id,
                machine_code=machine.machine_code if machine else "",
                status="running",
                input_text=request.message[:8000],
            )
            stream_db.add(run)
            stream_db.commit()
            stream_db.refresh(run)

            yield event(
                {
                    "type": "conversation",
                    "id": conversation.id,
                    "title": conversation.title,
                }
            )
            yield event(
                {
                    "type": "skill",
                    "skill_id": skill.skill_id if skill else None,
                    "name": skill.name if skill else "自动诊断",
                    "matched": bool(skill),
                }
            )
            if machine:
                yield event(
                    {
                        "type": "machine",
                        "machine_code": machine.machine_code,
                        "model_code": machine.model_code,
                        "customer_name": machine.customer_name,
                        "site_name": machine.site_name,
                    }
                )
            yield event({"type": "status", "text": "正在检索资料"})
            yield event({"type": "citations", "items": citations})

            tools, tool_data, fault = run_tools(
                stream_db, machine, request.message, citations
            )
            for item in tools:
                stream_db.add(
                    ToolCallLog(
                        conversation_id=conversation.id,
                        diagnosis_run_id=run.id,
                        tool_name=item["name"],
                        arguments_json=json.dumps(
                            item.get("arguments") or {}, ensure_ascii=False
                        )[:4000],
                        result_json=json.dumps(
                            item.get("data"), ensure_ascii=False
                        )[:8000],
                        ok=bool(item.get("ok")),
                    )
                )
                yield event(
                    {"type": "tool", "name": item["name"], "ok": item["ok"]}
                )
            stream_db.commit()

            result = compose(
                stream_db, request.message, machine, fault, citations, tool_data
            )
            request_id = request.service_request_id
            if request_id:
                linked = stream_db.get(ServiceRequest, request_id)
                if linked:
                    apply_diagnosis(linked, result, run.id, conversation.id)
                    result["service_request_no"] = linked.request_no
                    stream_db.commit()
            run.fault_id = result["fault_id"]
            run.fault_name = result["fault_name"]
            run.confidence = result["confidence"]
            run.on_site = result["on_site"]
            run.warranty_status = (result["warranty"] or {}).get("status", "")
            run.follow_up_count = len(result["follow_up"])
            run.tool_count = len(tools)
            run.diagnosis_json = json.dumps(result, ensure_ascii=False)[:20000]
            stream_db.commit()
            yield event({"type": "diagnosis", "data": result})

            model_call = ModelCall(
                conversation_id=conversation.id,
                provider=MODEL_PROVIDER,
                model=MODEL_NAME,
                status="running",
                input_chars=len(request.message)
                + sum(len(item["content"]) for item in history)
                + sum(len(item["text"]) for item in citations),
            )
            stream_db.add(model_call)
            stream_db.commit()
            stream_db.refresh(model_call)

            yield event({"type": "status", "text": "正在生成诊断结论"})
            started = time.perf_counter()
            for text in stream_answer(
                request.message,
                history,
                citations,
                result,
                tool_context_text(tools),
                request.answer_mode,
            ):
                answer_parts.append(text)
                yield event({"type": "delta", "text": text})

            answer = "".join(answer_parts)
            model_call.status = "completed"
            model_call.output_chars = len(answer)
            model_call.elapsed_ms = int((time.perf_counter() - started) * 1000)
            run.status = "completed"
            run.output_text = answer[:12000]
            run.finished_at = datetime.now()
            append_message(
                stream_db,
                conversation.id,
                "assistant",
                answer,
                {
                    "diagnosis": result,
                    "skill": {
                        "id": skill.skill_id if skill else None,
                        "name": skill.name if skill else "自动诊断",
                    },
                },
            )
            stream_db.commit()
            yield event({"type": "done", "conversation_id": conversation.id})
        except Exception as exc:  # noqa: BLE001
            stream_db.rollback()
            if model_call:
                model_call.status = "failed"
                model_call.error = f"{type(exc).__name__}: {exc}"
                stream_db.add(model_call)
            if run:
                run.status = "failed"
                run.error = f"{type(exc).__name__}: {exc}"
                stream_db.add(run)
            stream_db.commit()
            yield event(
                {"type": "error", "message": f"诊断未完成：{type(exc).__name__}: {exc}"}
            )
        finally:
            stream_db.close()

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Cache-Control": "no-cache"},
    )
