from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def normalize_result(result):
    texts = []
    scores = []
    boxes = []

    if result is None:
        return texts, scores, boxes

    # PaddleOCR 3.x predict() returns Result objects.
    for item in result if isinstance(result, list) else [result]:
        payload = None
        if hasattr(item, "json"):
            payload = item.json
        elif isinstance(item, dict):
            payload = item
        if isinstance(payload, dict) and "res" in payload:
            payload = payload["res"]
        if isinstance(payload, dict):
            texts.extend(payload.get("rec_texts") or [])
            scores.extend(payload.get("rec_scores") or [])
            boxes.extend(payload.get("rec_polys") or [])
            continue

        # PaddleOCR 2.x ocr() returns nested line lists.
        if isinstance(item, list):
            for line in item:
                if (
                    isinstance(line, (list, tuple))
                    and len(line) >= 2
                    and isinstance(line[1], (list, tuple))
                    and len(line[1]) >= 2
                ):
                    texts.append(str(line[1][0]))
                    scores.append(float(line[1][1]))
                    boxes.append(line[0])
    return texts, scores, boxes


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: ocr_worker.py image [image ...]")

    os.environ.setdefault("FLAGS_use_mkldnn", "0")
    os.environ.setdefault("FLAGS_use_onednn", "0")

    from paddleocr import PaddleOCR

    engine = PaddleOCR(
        lang="ch",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=True,
        enable_mkldnn=False,
        cpu_threads=4,
    )
    for image in sys.argv[1:]:
        path = str(Path(image).resolve())
        try:
            result = engine.predict(path)
        except AttributeError:
            result = engine.ocr(path)
        texts, scores, boxes = normalize_result(result)
        print(
            json.dumps(
                {
                    "image": path,
                    "texts": texts,
                    "scores": scores,
                    "boxes": boxes,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
