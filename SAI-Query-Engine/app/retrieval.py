from __future__ import annotations

from typing import Any


class ChunkRetriever:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def search(
        self,
        query_embedding: list[float],
        top_k: int,
    ) -> list[str]:
        import psycopg

        sql = """
            SELECT content
            FROM chunks
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %(embedding)s::vector
            LIMIT %(top_k)s
        """

        params: dict[str, Any] = {
            "embedding": _to_pgvector(query_embedding),
            "top_k": top_k,
        }

        with psycopg.connect(self.dsn) as conn:
            rows = conn.execute(sql, params).fetchall()

        return [row[0] for row in rows]


def build_context(chunks: list[str]) -> str:
    return "\n\n".join(chunks)


def _to_pgvector(embedding: list[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in embedding) + "]"