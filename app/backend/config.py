from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parent
APP_DIR = BACKEND_DIR.parent
PROJECT_DIR = APP_DIR.parent
FRONTEND_DIR = APP_DIR / "frontend"
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "app.db"

load_dotenv(APP_DIR / ".env")


def _resolve_path(value: str, default: Path) -> Path:
    """相对路径按项目根目录解析，避免受启动目录影响。"""
    if not value:
        return default.resolve()
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_DIR / path
    return path.resolve()


# 诊断数据集与 MCP 工具服务所在目录。
DIAGNOSTIC_DIR = _resolve_path(
    os.getenv("DIAGNOSTIC_DIR", ""), PROJECT_DIR / "remotediag"
)
DATA_PACK_DIR = _resolve_path(
    os.getenv("DATA_PACK_DIR", ""), DIAGNOSTIC_DIR / "数据包"
)

UPLOAD_DIR = _resolve_path(os.getenv("UPLOAD_DIR", ""), DATA_DIR / "uploads")
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 保修与到场时限的评估基准日，默认取初始数据集的窗口末日。
REFERENCE_DATE = os.getenv("REFERENCE_DATE", "2026-07-31").strip()

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH.as_posix()}")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "30"))

# 模型网关：业务代码只读这些配置，不直接依赖具体模型提供方。
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "deepseek").strip()
MODEL_BASE_URL = os.getenv("MODEL_BASE_URL", "https://api.deepseek.com").rstrip("/")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-chat").strip()
MODEL_API_KEY = os.getenv("MODEL_API_KEY", "").strip()
MODEL_TIMEOUT_SECONDS = int(os.getenv("MODEL_TIMEOUT_SECONDS", "120"))

# MCP 工具服务：诊断数据与设备状态由独立进程提供，产品后端不内嵌。
MCP_COMMAND = os.getenv("MCP_COMMAND", "python mcp_server.py")
MCP_WORKDIR = _resolve_path(os.getenv("MCP_WORKDIR", ""), DIAGNOSTIC_DIR)
MCP_DATA_DIR = os.getenv("MCP_DATA_DIR", str(DATA_PACK_DIR))

INITIAL_ADMIN_USER = os.getenv("INITIAL_ADMIN_USER", "admin")
INITIAL_ADMIN_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD", "admin_change_me")
SESSION_DAYS = int(os.getenv("SESSION_DAYS", "7"))

OCR_PYTHON = Path(os.getenv("OCR_PYTHON", r"D:\PaddleOCR\venv\Scripts\python.exe"))
OCR_HOME = Path(os.getenv("OCR_HOME", r"D:\PaddleOCR\models"))
OCR_CACHE = Path(os.getenv("OCR_CACHE", r"D:\PaddleOCR\cache"))
OCR_TEMP_DIR = Path(os.getenv("OCR_TEMP_DIR", str(DATA_DIR / "ocr")))
OCR_TEMP_DIR.mkdir(parents=True, exist_ok=True)

BGE_PYTHON = Path(os.getenv("BGE_PYTHON", r"D:\BGE-M3\venv\Scripts\python.exe"))
BGE_MODEL_PATH = Path(os.getenv("BGE_MODEL_PATH", r"D:\BGE-M3\models\bge-m3"))
BGE_CACHE = Path(os.getenv("BGE_CACHE", r"D:\BGE-M3\cache"))

RETRIEVAL_MODE = os.getenv("RETRIEVAL_MODE", "hybrid").lower()

EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))
# 向量存储后端：sqlite 用本地余弦检索，pgvector 用 PostgreSQL 的向量索引。
# 未显式配置时，按 DATABASE_URL 自动推断。
VECTOR_BACKEND = (
    os.getenv("VECTOR_BACKEND", "").strip().lower()
    or ("pgvector" if DATABASE_URL.startswith("postgresql") else "sqlite")
)
