from __future__ import annotations

import json

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator, UserDefinedType


class PgVectorType(UserDefinedType):
    """把列类型渲染成 pgvector 扩展的 `vector(n)`。"""

    cache_ok = True

    def __init__(self, dimension: int):
        self.dimension = int(dimension)

    def get_col_spec(self, **kw):
        return f"vector({self.dimension})"

    def __repr__(self) -> str:
        return f"PgVectorType({self.dimension})"


def format_literal(vector) -> str:
    """转成 pgvector 认的文本字面量，如 `[0.1,0.2]`。"""
    return "[" + ",".join(f"{float(value):.8g}" for value in vector) + "]"


class VectorType(TypeDecorator):
    """跨后端的向量列。

    SQLite 存 TEXT（JSON 数组，和旧字段格式一致），
    PostgreSQL 存 pgvector 的原生 `vector(n)`。
    """

    impl = Text
    cache_ok = True

    def __init__(self, dimension: int = 1024):
        super().__init__()
        self.dimension = int(dimension)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PgVectorType(self.dimension))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            return value
        values = [float(item) for item in value]
        if dialect.name == "postgresql":
            return format_literal(values)
        return json.dumps(values)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return [float(item) for item in value]
        return [float(item) for item in json.loads(value)]
