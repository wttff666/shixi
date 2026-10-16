from __future__ import annotations

import hashlib
import secrets
import shutil
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from config import MAX_UPLOAD_MB, OCR_TEMP_DIR, UPLOAD_DIR
from database import get_db
from deps import require_roles
from models import BackgroundTask, Document, DocumentChunk, OcrPage
from schemas import (
    ChunkOut,
    ChunkPreviewRequest,
    ChunkPreviewResponse,
    DocumentDetail,
    DocumentOut,
    OcrPageOut,
    OcrPagesUpdate,
    TaskOut,
)
from services.chunker import STRATEGIES, chunk_blocks
from services.audit import record_audit
from services.ocr import available as ocr_available
from services.parser import SUPPORTED_EXTENSIONS, parse_document
from services.task_runner import submit_ocr


router = APIRouter(
    prefix="/api",
    tags=["documents"],
    dependencies=[Depends(require_roles("kb_admin", "sys_admin"))],
)


def normalize_filename(filename: str) -> str:
    safe = Path(filename or "upload").name
    return safe or "upload"


def retry_unlink(path: Path, attempts: int = 10):
    for _ in range(attempts):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            time.sleep(0.2)


def document_out(document: Document) -> DocumentOut:
    return DocumentOut.model_validate(document)


def document_detail(document: Document, include_chunks: bool = True) -> DocumentDetail:
    chunks = [
        ChunkOut.model_validate(chunk)
        for chunk in sorted(document.chunks, key=lambda item: item.order_index)
    ] if include_chunks else []
    return DocumentDetail(
        **DocumentOut.model_validate(document).model_dump(),
        chunks=chunks,
        content_preview=(document.content_text or "")[:2000],
    )


def replace_chunks(
    db: Session,
    document: Document,
    drafts,
    published: bool,
) -> list[DocumentChunk]:
    db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document.id
    ).delete()
    chunks = []
    for draft in drafts:
        chunk = DocumentChunk(
            document_id=document.id,
            order_index=draft.order_index,
            section=draft.section,
            title=draft.title,
            content=draft.content,
            source_file=document.filename,
            page_start=draft.page_start,
            page_end=draft.page_end,
            citation=draft.citation,
            strategy=draft.strategy,
            content_hash=draft.content_hash,
            published=published,
        )
        db.add(chunk)
        chunks.append(chunk)
    document.chunk_strategy = drafts[0].strategy if drafts else document.chunk_strategy
    return chunks


def parse_and_chunk(document: Document):
    parsed = parse_document(Path(document.source_path))
    if parsed.error:
        document.status = "ocr_required"
        document.parse_method = parsed.method
        document.error = parsed.error
        document.content_text = ""
        return parsed, []
    document.content_text = "\n\n".join(item.text for item in parsed.blocks)
    drafts = chunk_blocks(
        parsed.blocks,
        document.filename,
        document.chunk_strategy,
        document.max_chars,
        document.overlap_chars,
    )
    document.parse_method = parsed.method
    document.error = ""
    document.status = "preview_ready"
    return parsed, drafts


@router.get("/chunk-strategies")
def chunk_strategies():
    return [{"id": key, "name": value} for key, value in STRATEGIES.items()]


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    documents = db.query(Document).order_by(Document.created_at.desc()).all()
    return [document_out(document) for document in documents]


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(document_id: int, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    return document_detail(document)


@router.post("/documents/upload", response_model=DocumentDetail)
async def upload_document(
    file: UploadFile = File(...),
    strategy: str = Form("punctuation"),
    max_chars: int = Form(800),
    overlap_chars: int = Form(100),
    db: Session = Depends(get_db),
    user=Depends(require_roles("kb_admin", "sys_admin")),
):
    filename = normalize_filename(file.filename or "")
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"暂不支持文件类型：{suffix}")
    if strategy not in STRATEGIES:
        raise HTTPException(status_code=400, detail="未知切片策略")

    stored_name = f"{secrets.token_hex(10)}{suffix}"
    target = UPLOAD_DIR / stored_name
    digest = hashlib.sha256()
    total = 0
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024

    try:
        with target.open("wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"文件超过 {MAX_UPLOAD_MB} MB 限制",
                    )
                digest.update(chunk)
                output.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise

    existing = db.query(Document).filter(Document.sha256 == digest.hexdigest()).first()
    if existing:
        target.unlink(missing_ok=True)
        return document_detail(existing)

    document = Document(
        filename=filename,
        stored_name=stored_name,
        source_path=str(target),
        media_type=file.content_type or "",
        size=total,
        sha256=digest.hexdigest(),
        status="parsed",
        chunk_strategy=strategy,
        max_chars=max_chars,
        overlap_chars=overlap_chars,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        _, drafts = await run_in_threadpool(parse_and_chunk, document)
        if drafts:
            replace_chunks(db, document, drafts, published=False)
        db.commit()
        db.refresh(document)
        record_audit(
            db,
            user_id=user.id,
            action="document.upload",
            entity_type="document",
            entity_id=document.id,
            detail={"filename": document.filename, "status": document.status},
        )
    except Exception as exc:
        document.status = "failed"
        document.error = f"{type(exc).__name__}: {exc}"
        db.commit()
        db.refresh(document)
    return document_detail(document)


@router.post(
    "/documents/{document_id}/preview",
    response_model=ChunkPreviewResponse,
)
async def preview_chunks(
    document_id: int,
    request: ChunkPreviewRequest,
    db: Session = Depends(get_db),
):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    if document.parse_method == "legacy_rag":
        chunks = [
            ChunkOut.model_validate(chunk)
            for chunk in sorted(document.chunks, key=lambda item: item.order_index)
        ]
        return ChunkPreviewResponse(
            document_id=document.id,
            strategy="legacy",
            max_chars=0,
            overlap_chars=0,
            chunks=chunks,
        )
    if not document.content_text:
        raise HTTPException(status_code=400, detail="文档没有可切片的文本")
    if request.strategy not in STRATEGIES:
        raise HTTPException(status_code=400, detail="未知切片策略")

    document.chunk_strategy = request.strategy
    document.max_chars = request.max_chars
    document.overlap_chars = request.overlap_chars
    parsed, drafts = await run_in_threadpool(parse_and_chunk, document)
    replace_chunks(db, document, drafts, published=False)
    document.status = "preview_ready"
    db.commit()
    db.refresh(document)
    chunks = [
        ChunkOut.model_validate(chunk)
        for chunk in sorted(document.chunks, key=lambda item: item.order_index)
    ]
    return ChunkPreviewResponse(
        document_id=document.id,
        strategy=document.chunk_strategy,
        max_chars=document.max_chars,
        overlap_chars=document.overlap_chars,
        chunks=chunks,
    )


@router.post("/documents/{document_id}/publish", response_model=DocumentOut)
def publish_document(
    document_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("kb_admin", "sys_admin")),
):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    if not document.chunks:
        raise HTTPException(status_code=400, detail="请先生成切片预览")
    document.published = True
    document.status = "published"
    for chunk in document.chunks:
        chunk.published = True
    db.commit()
    db.refresh(document)
    record_audit(
        db,
        user_id=user.id,
        action="document.publish",
        entity_type="document",
        entity_id=document.id,
    )
    return document_out(document)


@router.post("/documents/{document_id}/ocr", response_model=TaskOut, status_code=202)
def ocr_document(
    document_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("kb_admin", "sys_admin")),
):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    if Path(document.source_path).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="OCR 只用于 PDF 文档")
    if not ocr_available():
        raise HTTPException(status_code=503, detail="OCR 环境尚未安装")
    existing = (
        db.query(BackgroundTask)
        .filter(
            BackgroundTask.document_id == document_id,
            BackgroundTask.kind == "ocr",
            BackgroundTask.status.in_(("pending", "running")),
        )
        .first()
    )
    if existing:
        return existing
    task = submit_ocr(document_id)
    record_audit(
        db,
        user_id=user.id,
        action="document.ocr",
        entity_type="document",
        entity_id=document.id,
        detail={"task_id": task.id},
    )
    return task


@router.get("/documents/{document_id}/ocr-pages", response_model=list[OcrPageOut])
def get_ocr_pages(document_id: int, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    return (
        db.query(OcrPage)
        .filter(OcrPage.document_id == document_id)
        .order_by(OcrPage.page_number)
        .all()
    )


@router.put("/documents/{document_id}/ocr-pages", response_model=list[OcrPageOut])
def update_ocr_pages(
    document_id: int,
    request: OcrPagesUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("kb_admin", "sys_admin")),
):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    rows = (
        db.query(OcrPage)
        .filter(OcrPage.document_id == document_id)
        .all()
    )
    by_page = {row.page_number: row for row in rows}
    for page in request.pages:
        row = by_page.get(page.page_number)
        if row:
            row.text = page.text.strip()

    ordered = sorted(by_page.values(), key=lambda item: item.page_number)
    document.content_text = "\n\n".join(row.text for row in ordered if row.text)
    blocks = [
        type("Block", (), {"page": row.page_number, "text": row.text})()
        for row in ordered
        if row.text
    ]
    drafts = chunk_blocks(
        blocks,
        document.filename,
        document.chunk_strategy,
        document.max_chars,
        document.overlap_chars,
    )
    replace_chunks(db, document, drafts, published=False)
    document.status = "preview_ready"
    document.published = False
    db.commit()
    record_audit(
        db,
        user_id=user.id,
        action="document.ocr_review",
        entity_type="document",
        entity_id=document.id,
        detail={"pages": len(ordered)},
    )
    return ordered


@router.post("/documents/{document_id}/reprocess", response_model=DocumentDetail)
async def reprocess_document(document_id: int, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    if document.parse_method == "legacy_rag":
        raise HTTPException(status_code=400, detail="系统导入知识库不支持重新处理")
    try:
        _, drafts = await run_in_threadpool(parse_and_chunk, document)
        replace_chunks(db, document, drafts, published=False)
        document.published = False
        db.commit()
        db.refresh(document)
    except Exception as exc:
        document.status = "failed"
        document.error = f"{type(exc).__name__}: {exc}"
        db.commit()
        db.refresh(document)
    return document_detail(document)


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("kb_admin", "sys_admin")),
):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    if document.parse_method == "legacy_rag":
        raise HTTPException(status_code=400, detail="系统导入知识库不能删除")
    source = Path(document.source_path)
    db.delete(document)
    db.commit()
    retry_unlink(source)
    shutil.rmtree(OCR_TEMP_DIR / str(document_id), ignore_errors=True)
    record_audit(
        db,
        user_id=user.id,
        action="document.delete",
        entity_type="document",
        entity_id=document_id,
    )
    return {"ok": True}
