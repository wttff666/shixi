from __future__ import annotations

import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import Conversation, Message


def get_owned_conversation(db: Session, conversation_id: int, user_id: int):
    conversation = db.get(Conversation, conversation_id)
    if not conversation or conversation.user_id != user_id:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conversation


def create_conversation(db: Session, user_id: int, title: str = "新对话"):
    conversation = Conversation(user_id=user_id, title=title.strip() or "新对话")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def append_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
    meta=None,
):
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        meta_json=json.dumps(meta or {}, ensure_ascii=False),
    )
    db.add(message)
    conversation = db.get(Conversation, conversation_id)
    if conversation:
        conversation.updated_at = datetime.now()
    db.commit()
    db.refresh(message)
    return message


def message_view(message: Message):
    try:
        meta = json.loads(message.meta_json or "{}")
    except ValueError:
        meta = {}
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "meta": meta,
        "created_at": message.created_at,
    }
