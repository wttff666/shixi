from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path

from config import BGE_CACHE, BGE_MODEL_PATH, BGE_PYTHON


WORKER = Path(__file__).resolve().parent / "embedding_worker.py"
_process = None
_lock = threading.Lock()


def available():
    return BGE_PYTHON.exists() and BGE_MODEL_PATH.exists() and WORKER.exists()


def embed_texts(texts):
    if not available():
        raise RuntimeError(
            f"BGE-M3 环境不可用：python={BGE_PYTHON}, model={BGE_MODEL_PATH}"
        )
    global _process
    with _lock:
        if _process is None or _process.poll() is not None:
            env = os.environ.copy()
            env["HF_HOME"] = str(BGE_CACHE / "huggingface")
            env["HF_ENDPOINT"] = env.get(
                "HF_ENDPOINT",
                "https://hf-mirror.com",
            )
            env["PYTHONIOENCODING"] = "utf-8"
            _process = subprocess.Popen(
                [str(BGE_PYTHON), str(WORKER)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(WORKER.parent),
                env=env,
                bufsize=1,
            )
        assert _process.stdin and _process.stdout
        _process.stdin.write(
            json.dumps(
                {"texts": texts, "model_path": str(BGE_MODEL_PATH)},
                ensure_ascii=False,
            )
            + "\n"
        )
        _process.stdin.flush()
        line = _process.stdout.readline()
        if not line:
            error = ""
            if _process.stderr:
                try:
                    error = _process.stderr.read(1000)
                except OSError:
                    pass
            raise RuntimeError(f"Embedding Worker 已退出：{error}")
        payload = json.loads(line)
        return payload["vectors"], int(payload["dimension"])
