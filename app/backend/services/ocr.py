from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from config import OCR_CACHE, OCR_HOME, OCR_PYTHON, OCR_TEMP_DIR
from services.parser import ParsedBlock, ParsedDocument, clean_text


WORKER = Path(__file__).resolve().parent / "ocr_worker.py"


@dataclass
class OcrPageData:
    page_number: int
    text: str
    confidence: float
    boxes: list = field(default_factory=list)


@dataclass
class OcrDocumentResult:
    method: str
    pages: list[OcrPageData]
    error: str = ""

    def parsed_blocks(self):
        return [
            ParsedBlock(page.page_number, page.text)
            for page in self.pages
            if page.text
        ]


def available():
    return OCR_PYTHON.exists() and WORKER.exists()


def render_pdf_pages(path: Path, output_dir: Path):
    import pymupdf

    output_dir.mkdir(parents=True, exist_ok=True)
    images = []
    with pymupdf.open(path) as document:
        for page_number, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
            image_path = output_dir / f"page-{page_number:04d}.png"
            pixmap.save(image_path)
            images.append(image_path)
    return images


def run_pdf_ocr(path: Path, document_id: int):
    if not available():
        return OcrDocumentResult(
            "pdf_ocr_unavailable",
            [],
            f"OCR 环境不可用：{OCR_PYTHON}",
        )

    work_dir = OCR_TEMP_DIR / str(document_id)
    images = render_pdf_pages(path, work_dir)
    env = os.environ.copy()
    env["PADDLEOCR_HOME"] = str(OCR_HOME)
    env["PADDLE_PDX_CACHE_HOME"] = str(OCR_HOME)
    env["PADDLEX_HOME"] = str(OCR_CACHE / "paddlex")
    env["HF_HOME"] = str(OCR_CACHE / "huggingface")
    env["PYTHONIOENCODING"] = "utf-8"

    process = subprocess.run(
        [str(OCR_PYTHON), str(WORKER), *map(str, images)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(WORKER.parent),
        env=env,
        timeout=600,
    )
    if process.returncode != 0:
        return OcrDocumentResult(
            "pdf_ocr_failed",
            [],
            (process.stderr or process.stdout or "OCR 执行失败")[-1000:],
        )

    pages = []
    for line in process.stdout.splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        page_number = int(Path(payload["image"]).stem.split("-")[-1])
        text = clean_text("\n".join(payload.get("texts") or []))
        scores = [float(value) for value in payload.get("scores") or []]
        confidence = sum(scores) / len(scores) if scores else 0.0
        pages.append(
            OcrPageData(
                page_number=page_number,
                text=text,
                confidence=confidence,
                boxes=payload.get("boxes") or [],
            )
        )
    if not any(page.text for page in pages):
        return OcrDocumentResult(
            "pdf_ocr_empty",
            [],
            "OCR 完成但没有识别到文字。",
        )
    return OcrDocumentResult("pdf_ocr", pages)
