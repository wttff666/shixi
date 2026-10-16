from __future__ import annotations

from sqlalchemy.orm import Session

from config import RETRIEVAL_MODE
from services.hybrid_retrieval import search_hybrid
from services.retrieval import search as lexical_search


def retrieve(db: Session, query: str, limit: int = 5):
    if RETRIEVAL_MODE == "hybrid":
        return search_hybrid(db, query, limit=limit)
    return lexical_search(db, query, limit=limit)
