from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from services.embedding import available, embed_texts  # noqa: E402
from services.vector_store import cosine_similarity  # noqa: E402
from services.vector_types import format_literal  # noqa: E402


def test_cosine_similarity_bounds():
    assert cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)
    assert cosine_similarity([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0)
    assert cosine_similarity([0, 0, 0], [1, 0, 0]) == 0.0
    assert cosine_similarity([1, 2], [1, 2, 3]) == 0.0


def test_pgvector_literal_format():
    literal = format_literal([0.5, -1.25, 2.0])
    assert literal.startswith("[") and literal.endswith("]")
    assert literal.count(",") == 2


def test_embedding_dimension():
    if not available():
        pytest.skip("BGE-M3 环境不可用，跳过向量维度检查")
    vectors, dimension = embed_texts(["液压油温过高", "冷却水流量不足"])
    assert dimension == 1024
    assert len(vectors) == 2
    assert len(vectors[0]) == dimension
    assert cosine_similarity(vectors[0], vectors[0]) == pytest.approx(1.0, abs=1e-4)
