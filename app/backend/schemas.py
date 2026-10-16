from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# --- 知识库 -------------------------------------------------------------


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_index: int
    section: str
    title: str
    content: str
    source_file: str
    page_start: int
    page_end: int
    citation: str
    strategy: str
    published: bool


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    media_type: str
    size: int
    status: str
    parse_method: str
    error: str
    chunk_strategy: str
    max_chars: int
    overlap_chars: int
    published: bool
    created_at: datetime
    updated_at: datetime


class DocumentDetail(DocumentOut):
    chunks: list[ChunkOut] = []
    content_preview: str = ""


class ChunkPreviewRequest(BaseModel):
    strategy: str = "punctuation"
    max_chars: int = Field(default=800, ge=100, le=5000)
    overlap_chars: int = Field(default=100, ge=0, le=1000)


class ChunkPreviewResponse(BaseModel):
    document_id: int
    strategy: str
    max_chars: int
    overlap_chars: int
    chunks: list[ChunkOut]


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    status: str
    document_id: int | None
    progress: int
    message: str
    error: str
    created_at: datetime
    updated_at: datetime


class OcrPageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_number: int
    text: str
    confidence: float


class OcrPagesUpdate(BaseModel):
    pages: list[OcrPageOut]


# --- 主数据 -------------------------------------------------------------


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    level: str
    region: str
    city: str
    site: str
    service_level: str


class MachineModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    clamp_force: int
    screw_diameter: int
    shot_size: int
    launch_year: int


class WarrantyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    warranty_type: str
    coverage: str
    service_level: str
    warranty_end: str
    status: str = ""


class MachineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    machine_code: str
    model_code: str
    model_name: str
    serial_no: str
    customer_name: str
    site_name: str
    line_name: str
    production_date: str
    install_date: str
    status: str
    firmware: str
    last_service_at: str
    warranty_status: str = ""
    warranty_end: str = ""


class SparePartOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    part_no: str
    name: str
    spec: str
    applicable_models: str
    supplier: str
    unit_price: int
    stock: int
    lead_days: int


class ServiceBulletinOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bulletin_no: str
    applicable_models: str
    applicable_batch: str
    description: str
    action: str
    hint: str
    valid_until: str


class FaultDefinitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fault_id: str
    code: str
    name: str
    group_name: str
    severity: str
    alarm_condition: str
    key_params: str
    manual_section: str
    reset_method: str
    part_no: str
    on_site: str
    questions: list[str] = []
    steps: list[str] = []


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticket_no: str
    machine_code: str
    customer_name: str
    model_code: str
    warranty_status: str
    reported_at: str
    fault_id: str
    symptom: str
    cause: str
    action: str
    manual_section: str
    on_site: str
    parts: str
    hours: str
    settlement: str
    cost: int


# --- 诊断 ---------------------------------------------------------------


class DiagnosisRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    conversation_id: int | None = None
    service_request_id: int | None = None
    machine_code: str | None = None
    skill_id: str | None = None
    answer_mode: str = "standard"


class Citation(BaseModel):
    chunk_id: int
    ref: str
    section: str
    title: str
    source: str
    text: str
    score: float


class PartSuggestion(BaseModel):
    part_no: str
    name: str
    spec: str = ""
    stock: int = 0
    lead_days: int = 0
    unit_price: int = 0


class WarrantyDecision(BaseModel):
    status: str = ""
    settlement: str = ""
    service_level: str = ""
    warranty_end: str = ""


class BulletinHint(BaseModel):
    bulletin_no: str
    hint: str
    action: str
    valid_until: str


class DispatchAdvice(BaseModel):
    """派工建议：客服决定远程指导还是安排到场。"""

    mode: str = ""
    reason: str = ""
    sla: str = ""
    response_hours: int = 0
    onsite_hours: int = 0
    eta_hours: str = ""
    eta_basis: str = ""
    second_line: bool = False
    second_line_reason: str = ""
    parts: list[PartSuggestion] = []


class DiagnosisResult(BaseModel):
    machine_code: str = ""
    model_code: str = ""
    customer_name: str = ""
    service_request_no: str = ""
    fault_id: str = ""
    fault_name: str = ""
    severity: str = ""
    manual_section: str = ""
    cause: str = ""
    action: str = ""
    risk: str = ""
    on_site: str = ""
    confidence: str = ""
    parts: list[PartSuggestion] = []
    warranty: WarrantyDecision = WarrantyDecision()
    bulletin: BulletinHint | None = None
    dispatch: DispatchAdvice = DispatchAdvice()
    follow_up: list[str] = []
    missing: list[str] = []
    internal_notes: list[str] = []
    customer_reply: str = ""
    citations: list[Citation] = []
    similar_tickets: list[dict[str, Any]] = []


# --- 会话 ---------------------------------------------------------------


class ConversationCreate(BaseModel):
    title: str = "新诊断"


class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=300)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    meta: dict[str, Any] = {}
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = []


# --- 账号 ---------------------------------------------------------------


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=200)
    role: str = "agent"
    customer_name: str = ""


class UserUpdate(BaseModel):
    role: str | None = None
    active: bool | None = None
    customer_name: str | None = None


class PasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=200)


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    role_label: str
    customer_name: str
    active: bool
    must_change_password: bool
    created_at: datetime


# --- Skill --------------------------------------------------------------


class SkillCreate(BaseModel):
    id: str = Field(min_length=2, max_length=100)
    name: str = Field(min_length=2, max_length=200)
    version: str = "1.0.0"
    description: str = ""
    instructions: str = ""
    allowed_tools: list[str] = []
    retrieval_scope: list[str] = []
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}
    response_template: str = ""
    examples: list[dict[str, Any]] = []


class SkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    skill_id: str
    name: str
    version: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime


# --- 服务工单 -----------------------------------------------------------


class ServiceRequestCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=200)
    machine_code: str = Field(min_length=1, max_length=50)
    channel: str = "电话"
    priority: str = "普通"
    symptom: str = Field(min_length=1, max_length=5000)


class ServiceRequestUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    channel: str | None = None
    handler_name: str | None = None
    closed_note: str | None = None


class ServiceRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_no: str
    customer_name: str
    machine_code: str
    model_code: str
    channel: str
    priority: str
    status: str
    symptom: str
    handler_name: str
    fault_id: str
    fault_name: str
    confidence: str
    on_site: str
    customer_reply: str = ""
    conversation_id: int | None = None
    created_at: datetime
    updated_at: datetime


class ServiceRequestDetail(ServiceRequestOut):
    dispatch: dict[str, Any] = {}
    customer_reply: str = ""
    internal_notes: list[str] = []
    closed_note: str = ""
    conversation_id: int | None = None
    citations: list[Citation] = []
    similar_tickets: list[dict[str, Any]] = []
