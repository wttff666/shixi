from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from database import SessionLocal
from models import BackgroundTask, Document, DocumentChunk, OcrPage
from services.chunker import chunk_blocks
from services.ocr import run_pdf_ocr


executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wind-task")


def mark_running_tasks_failed():
    db = SessionLocal()
    try:
        tasks = (
            db.query(BackgroundTask)
            .filter(BackgroundTask.status.in_(("pending", "running")))
            .all()
        )
        for task in tasks:
            task.status = "failed"
            task.error = "服务重启，任务已中断，请重试。"
            task.message = "任务中断"
        db.commit()
    finally:
        db.close()


def submit_ocr(document_id: int):
    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if not document:
            raise ValueError("文档不存在")
        task = BackgroundTask(
            kind="ocr",
            status="pending",
            document_id=document_id,
            progress=0,
            message="等待 OCR 任务",
        )
        db.add(task)
        document.status = "ocr_pending"
        document.error = ""
        db.commit()
        db.refresh(task)
        executor.submit(run_ocr_task, task.id, document_id)
        return task
    finally:
        db.close()


def store_ocr_pages(db, document: Document, result):
    db.query(OcrPage).filter(OcrPage.document_id == document.id).delete()
    for page in result.pages:
        db.add(
            OcrPage(
                document_id=document.id,
                page_number=page.page_number,
                text=page.text,
                confidence=page.confidence,
                boxes_json=json.dumps(page.boxes, ensure_ascii=False),
            )
        )


def replace_document_chunks(db, document: Document, drafts):
    db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document.id
    ).delete()
    for draft in drafts:
        db.add(
            DocumentChunk(
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
                published=False,
            )
        )


def run_ocr_task(task_id: int, document_id: int):
    db = SessionLocal()
    try:
        task = db.get(BackgroundTask, task_id)
        document = db.get(Document, document_id)
        if not task or not document:
            return
        task.status = "running"
        task.progress = 10
        task.message = "正在渲染并识别扫描页"
        db.commit()

        result = run_pdf_ocr(Path(document.source_path), document.id)
        if result.error:
            task.status = "failed"
            task.progress = 100
            task.message = "OCR 失败"
            task.error = result.error
            document.status = "ocr_required"
            document.parse_method = result.method
            document.error = result.error
            db.commit()
            return

        task.progress = 80
        task.message = "正在写入 OCR 结果和切片"
        db.commit()
        store_ocr_pages(db, document, result)
        document.content_text = "\n\n".join(
            page.text for page in result.pages if page.text
        )
        drafts = chunk_blocks(
            result.parsed_blocks(),
            document.filename,
            document.chunk_strategy,
            document.max_chars,
            document.overlap_chars,
        )
        replace_document_chunks(db, document, drafts)
        document.status = "preview_ready"
        document.parse_method = "pdf_ocr"
        document.error = ""
        document.published = False
        task.status = "completed"
        task.progress = 100
        task.message = f"OCR 完成，共 {len(result.pages)} 页、{len(drafts)} 个切片"
        task.result_json = json.dumps(
            {
                "page_count": len(result.pages),
                "chunk_count": len(drafts),
            },
            ensure_ascii=False,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        task = db.get(BackgroundTask, task_id)
        document = db.get(Document, document_id)
        if task:
            task.status = "failed"
            task.progress = 100
            task.message = "OCR 异常"
            task.error = f"{type(exc).__name__}: {exc}"
        if document:
            document.status = "ocr_required"
            document.error = f"{type(exc).__name__}: {exc}"
        db.commit()
    finally:
        db.close()
