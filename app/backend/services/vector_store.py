from __future__ import annotations

import math

from sqlalchemy import text
from sqlalchemy.orm import Session

from config import VECTOR_BACKEND
from models import ChunkEmbedding, DocumentChunk
from services.embedding import embed_texts
from services.vector_types import format_literal


PGVECTOR_SEARCH_SQL = text(
    """
    SELECT
        chunk.id AS chunk_id,
        chunk.citation AS ref,
        chunk.section AS section,
        chunk.title AS title,
        chunk.source_file AS source,
        chunk.content AS text,
        1 - (embedding.vector <=> (:query)::vector) AS vector_score
    FROM chunk_embeddings AS embedding
    JOIN document_chunks AS chunk ON chunk.id = embedding.chunk_id
    WHERE chunk.published IS TRUE
    ORDER BY embedding.vector <=> (:query)::vector
    LIMIT :limit
    """
)

PGVECTOR_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS chunk_embeddings_vector_idx "
    "ON chunk_embeddings USING hnsw (vector vector_cosine_ops)"
)


def vector_norm(vector):
    return math.sqrt(sum(value * value for value in vector))


def cosine_similarity(left, right):
    if len(left) != len(right):
        return 0.0
    denominator = vector_norm(left) * vector_norm(right)
    if not denominator:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / denominator


def rebuild_embeddings(db: Session, model_name: str, batch_size: int = 64):
    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.published.is_(True))
        .order_by(DocumentChunk.id)
        .all()
    )
    db.query(ChunkEmbedding).delete()
    db.commit()
    total = 0
    dimension = 0
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        vectors, dimension = embed_texts(
            [
                f"{chunk.title}\n{chunk.content}"
                for chunk in batch
            ]
        )
        for chunk, vector in zip(batch, vectors):
            db.add(
                ChunkEmbedding(
                    chunk_id=chunk.id,
                    model=model_name,
                    dimension=dimension,
                    content_hash=chunk.content_hash,
                    vector=vector,
                )
            )
            total += 1
        db.commit()
    ensure_vector_index(db)
    return {
        "chunk_count": len(chunks),
        "embedded_count": total,
        "dimension": dimension,
        "model": model_name,
    }


def ensure_vector_index(db: Session):
    """pgvector 后端下建立余弦索引；SQLite 后端什么也不做。"""
    if VECTOR_BACKEND != "pgvector":
        return False
    db.execute(text(PGVECTOR_INDEX_SQL))
    db.commit()
    return True


def pgvector_search(db: Session, query_vector, limit: int = 5):
    rows = db.execute(
        PGVECTOR_SEARCH_SQL,
        {"query": format_literal(query_vector), "limit": limit},
    ).mappings().all()
    results = []
    for row in rows:
        score = max(0.0, min(1.0, float(row["vector_score"] or 0.0)))
        results.append(
            {
                "chunk_id": row["chunk_id"],
                "ref": row["ref"],
                "section": row["section"],
                "title": row["title"],
                "source": row["source"],
                "text": row["text"],
                "score": score,
                "vector_score": score,
            }
        )
    return results


def sqlite_vector_search(db: Session, query_vector, limit: int = 5):
    rows = (
        db.query(ChunkEmbedding, DocumentChunk)
        .join(DocumentChunk, DocumentChunk.id == ChunkEmbedding.chunk_id)
        .filter(DocumentChunk.published.is_(True))
        .all()
    )
    scored = []
    for embedding, chunk in rows:
        try:
            vector = [float(item) for item in embedding.vector]
        except (TypeError, ValueError):
            continue
        score = cosine_similarity(query_vector, vector)
        scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "chunk_id": chunk.id,
            "ref": chunk.citation,
            "section": chunk.section,
            "title": chunk.title,
            "source": chunk.source_file,
            "text": chunk.content,
            "score": float(score),
            "vector_score": float(score),
        }
        for score, chunk in scored[:limit]
    ]


def vector_search(db: Session, query_vector, limit: int = 5):
    if VECTOR_BACKEND == "pgvector":
        return pgvector_search(db, query_vector, limit=limit)
    return sqlite_vector_search(db, query_vector, limit=limit)
