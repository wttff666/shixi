from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config import EMBEDDING_DIM
from database import Base
from services.vector_types import VectorType


def now_local():
    """统一使用本地时间。系统按单一时区部署，避免接口返回 UTC 却被当作本地时间展示。"""
    return datetime.now()


# --- 主数据 -------------------------------------------------------------


class Customer(Base):
    """客户（设备使用方）。"""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    level: Mapped[str] = mapped_column(String(50), default="")
    region: Mapped[str] = mapped_column(String(50), default="")
    city: Mapped[str] = mapped_column(String(100), default="")
    site: Mapped[str] = mapped_column(String(200), default="")
    site_code: Mapped[str] = mapped_column(String(50), default="", index=True)
    service_level: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local
    )


class MachineModel(Base):
    """机型谱系。"""

    __tablename__ = "machine_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    clamp_force: Mapped[int] = mapped_column(Integer, default=0)
    screw_diameter: Mapped[int] = mapped_column(Integer, default=0)
    shot_size: Mapped[int] = mapped_column(Integer, default=0)
    launch_year: Mapped[int] = mapped_column(Integer, default=0)


class Machine(Base):
    """设备档案。"""

    __tablename__ = "machines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    machine_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    model_code: Mapped[str] = mapped_column(String(100), index=True)
    model_name: Mapped[str] = mapped_column(String(200), default="")
    serial_no: Mapped[str] = mapped_column(String(100), default="", index=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    customer_name: Mapped[str] = mapped_column(String(200), default="", index=True)
    site_name: Mapped[str] = mapped_column(String(200), default="")
    line_name: Mapped[str] = mapped_column(String(100), default="")
    production_date: Mapped[str] = mapped_column(String(50), default="")
    install_date: Mapped[str] = mapped_column(String(50), default="")
    status: Mapped[str] = mapped_column(String(50), default="")
    firmware: Mapped[str] = mapped_column(String(100), default="")
    last_service_at: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local
    )

    warranty: Mapped["Warranty | None"] = relationship(
        back_populates="machine", uselist=False
    )


class Warranty(Base):
    """保修与服务合同。"""

    __tablename__ = "warranties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE"), unique=True, index=True
    )
    warranty_type: Mapped[str] = mapped_column(String(100), default="")
    coverage: Mapped[str] = mapped_column(String(300), default="")
    service_level: Mapped[str] = mapped_column(String(100), default="")
    warranty_end: Mapped[str] = mapped_column(String(50), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local, onupdate=now_local
    )

    machine: Mapped[Machine] = relationship(back_populates="warranty")


class SparePart(Base):
    """备件主数据。"""

    __tablename__ = "spare_parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    spec: Mapped[str] = mapped_column(String(300), default="")
    applicable_models: Mapped[str] = mapped_column(String(300), default="")
    supplier: Mapped[str] = mapped_column(String(200), default="")
    unit_price: Mapped[int] = mapped_column(Integer, default=0)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    lead_days: Mapped[int] = mapped_column(Integer, default=0)


class ServiceBulletin(Base):
    """批次性服务通报。"""

    __tablename__ = "service_bulletins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bulletin_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    applicable_models: Mapped[str] = mapped_column(String(200), default="")
    applicable_batch: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[str] = mapped_column(Text, default="")
    hint: Mapped[str] = mapped_column(Text, default="")
    valid_until: Mapped[str] = mapped_column(String(50), default="")


class FaultDefinition(Base):
    """故障定义（故障树节点），用于结构化诊断与追问。"""

    __tablename__ = "fault_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fault_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    code: Mapped[str] = mapped_column(String(200), default="")
    name: Mapped[str] = mapped_column(String(200))
    group_name: Mapped[str] = mapped_column(String(100), default="")
    severity: Mapped[str] = mapped_column(String(50), default="")
    alarm_condition: Mapped[str] = mapped_column(String(300), default="")
    key_params: Mapped[str] = mapped_column(String(300), default="")
    manual_section: Mapped[str] = mapped_column(String(50), default="", index=True)
    reset_method: Mapped[str] = mapped_column(String(200), default="")
    part_no: Mapped[str] = mapped_column(String(50), default="")
    on_site: Mapped[str] = mapped_column(String(10), default="")
    keywords: Mapped[str] = mapped_column(String(500), default="")
    cause: Mapped[str] = mapped_column(Text, default="")
    risk: Mapped[str] = mapped_column(Text, default="")
    questions_json: Mapped[str] = mapped_column(Text, default="[]")
    steps_json: Mapped[str] = mapped_column(Text, default="[]")


class Ticket(Base):
    """历史服务工单，用于相似案例检索与知识沉淀。"""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    machine_code: Mapped[str] = mapped_column(String(50), default="", index=True)
    customer_name: Mapped[str] = mapped_column(String(200), default="", index=True)
    model_code: Mapped[str] = mapped_column(String(100), default="")
    warranty_status: Mapped[str] = mapped_column(String(50), default="")
    reported_at: Mapped[str] = mapped_column(String(50), default="")
    fault_id: Mapped[str] = mapped_column(String(50), default="", index=True)
    symptom: Mapped[str] = mapped_column(Text, default="")
    anomaly: Mapped[str] = mapped_column(Text, default="")
    cause: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[str] = mapped_column(Text, default="")
    manual_section: Mapped[str] = mapped_column(String(50), default="")
    on_site: Mapped[str] = mapped_column(String(10), default="")
    parts: Mapped[str] = mapped_column(String(300), default="")
    hours: Mapped[str] = mapped_column(String(20), default="")
    settlement: Mapped[str] = mapped_column(String(50), default="")
    cost: Mapped[int] = mapped_column(Integer, default=0)


# --- 知识库 -------------------------------------------------------------


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(500))
    stored_name: Mapped[str] = mapped_column(String(500), unique=True)
    source_path: Mapped[str] = mapped_column(String(1000))
    media_type: Mapped[str] = mapped_column(String(200), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(50), default="uploaded", index=True)
    parse_method: Mapped[str] = mapped_column(String(100), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    content_text: Mapped[str] = mapped_column(Text, default="")
    chunk_strategy: Mapped[str] = mapped_column(String(50), default="punctuation")
    max_chars: Mapped[int] = mapped_column(Integer, default=800)
    overlap_chars: Mapped[int] = mapped_column(Integer, default=100)
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local, onupdate=now_local
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    order_index: Mapped[int] = mapped_column(Integer)
    section: Mapped[str] = mapped_column(String(100), default="")
    title: Mapped[str] = mapped_column(String(500), default="")
    content: Mapped[str] = mapped_column(Text)
    source_file: Mapped[str] = mapped_column(String(500), default="")
    page_start: Mapped[int] = mapped_column(Integer, default=1)
    page_end: Mapped[int] = mapped_column(Integer, default=1)
    citation: Mapped[str] = mapped_column(String(1000), default="")
    strategy: Mapped[str] = mapped_column(String(50), default="punctuation")
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local
    )

    document: Mapped[Document] = relationship(back_populates="chunks")


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_id: Mapped[int] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), unique=True, index=True
    )
    model: Mapped[str] = mapped_column(String(300))
    dimension: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    vector: Mapped[list] = mapped_column(VectorType(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local
    )


# --- 账号与安全 ---------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    password_salt: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(50), default="agent", index=True)
    customer_name: Mapped[str] = mapped_column(String(200), default="", index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local, onupdate=now_local
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(100), default="")
    entity_id: Mapped[str] = mapped_column(String(200), default="")
    detail_json: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local
    )


# --- 会话与诊断 ---------------------------------------------------------


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(300), default="新诊断")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local, onupdate=now_local
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    meta_json: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local
    )


class DiagnosisRun(Base):
    """一次诊断运行，记录结论与依据，用于审计与指标统计。"""

    __tablename__ = "diagnosis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    machine_code: Mapped[str] = mapped_column(String(50), default="", index=True)
    fault_id: Mapped[str] = mapped_column(String(50), default="", index=True)
    fault_name: Mapped[str] = mapped_column(String(200), default="")
    confidence: Mapped[str] = mapped_column(String(30), default="")
    on_site: Mapped[str] = mapped_column(String(10), default="")
    warranty_status: Mapped[str] = mapped_column(String(50), default="")
    follow_up_count: Mapped[int] = mapped_column(Integer, default=0)
    tool_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="running", index=True)
    input_text: Mapped[str] = mapped_column(Text, default="")
    diagnosis_json: Mapped[str] = mapped_column(Text, default="")
    output_text: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ModelCall(Base):
    __tablename__ = "model_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(100), default="")
    model: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(50), default="running")
    input_chars: Mapped[int] = mapped_column(Integer, default=0)
    output_chars: Mapped[int] = mapped_column(Integer, default=0)
    elapsed_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local
    )


class ToolCallLog(Base):
    __tablename__ = "tool_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    diagnosis_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("diagnosis_runs.id", ondelete="SET NULL"), nullable=True
    )
    tool_name: Mapped[str] = mapped_column(String(200), index=True)
    arguments_json: Mapped[str] = mapped_column(Text, default="")
    result_json: Mapped[str] = mapped_column(Text, default="")
    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    elapsed_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local
    )


# --- 声明式 Skill（诊断技能配置）---------------------------------------


class ServiceRequest(Base):
    """服务工单：客服中心的工作单位，诊断结论挂在工单下。"""

    __tablename__ = "service_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(200), default="", index=True)
    machine_code: Mapped[str] = mapped_column(String(50), default="", index=True)
    model_code: Mapped[str] = mapped_column(String(100), default="")
    channel: Mapped[str] = mapped_column(String(50), default="电话")
    priority: Mapped[str] = mapped_column(String(50), default="普通")
    status: Mapped[str] = mapped_column(String(50), default="待研判", index=True)
    symptom: Mapped[str] = mapped_column(Text, default="")
    handler_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    handler_name: Mapped[str] = mapped_column(String(100), default="")
    fault_id: Mapped[str] = mapped_column(String(50), default="")
    fault_name: Mapped[str] = mapped_column(String(200), default="")
    confidence: Mapped[str] = mapped_column(String(30), default="")
    on_site: Mapped[str] = mapped_column(String(10), default="")
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    diagnosis_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("diagnosis_runs.id", ondelete="SET NULL"), nullable=True
    )
    dispatch_json: Mapped[str] = mapped_column(Text, default="")
    customer_reply: Mapped[str] = mapped_column(Text, default="")
    internal_notes_json: Mapped[str] = mapped_column(Text, default="[]")
    closed_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local, onupdate=now_local
    )


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill_id: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(300))
    version: Mapped[str] = mapped_column(String(100), default="1.0.0")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    config_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local, onupdate=now_local
    )


# --- 后台任务与 OCR -----------------------------------------------------


class BackgroundTask(Base):
    __tablename__ = "background_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(String(500), default="")
    result_json: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local, onupdate=now_local
    )


class OcrPage(Base):
    __tablename__ = "ocr_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(default=0.0)
    boxes_json: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local, onupdate=now_local
    )
