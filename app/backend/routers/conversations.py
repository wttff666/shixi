from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from deps import get_current_user
from models import Conversation, Message
from schemas import (
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    ConversationRename,
)
from services.conversation import (
    create_conversation,
    get_owned_conversation,
    message_view,
)


router = APIRouter(prefix="/api", tags=["conversations"])


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


@router.post("/conversations", response_model=ConversationOut)
def new_conversation(
    request: ConversationCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return create_conversation(db, user.id, request.title)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def conversation_detail(
    conversation_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    conversation = get_owned_conversation(db, conversation_id, user.id)
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.id)
        .all()
    )
    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "messages": [message_view(message) for message in messages],
    }


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
def rename_conversation(
    conversation_id: int,
    request: ConversationRename,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    conversation = get_owned_conversation(db, conversation_id, user.id)
    conversation.title = request.title.strip()
    db.commit()
    db.refresh(conversation)
    return conversation


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    conversation = get_owned_conversation(db, conversation_id, user.id)
    db.delete(conversation)
    db.commit()
    return {"ok": True}
