from __future__ import annotations

import json
from typing import Any

from .models import Citation


class ChunkRetriever:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        client_id: str | None = None,
        file_id: str | None = None,
    ) -> list[Citation]:
        import psycopg

        filters = []
        params: dict[str, Any] = {
            "embedding": _to_pgvector(query_embedding),
            "top_k": top_k,
        }
        if client_id:
            filters.append("client_id = %(client_id)s")
            params["client_id"] = client_id
        if file_id:
            filters.append("file_id = %(file_id)s")
            params["file_id"] = file_id
        
        #dynamically add filters
        where_clause = "WHERE embedding IS NOT NULL"
        if filters:
            where_clause += " AND " + " AND ".join(filters)

        sql = f"""
            SELECT
                chunk_id::text,
                file_id,
                filename,
                page_start,
                page_end,
                chunk_index,
                content,
                metadata,
                1 - (embedding <=> %(embedding)s::vector) AS similarity
            FROM chunks
            {where_clause}
            ORDER BY embedding <=> %(embedding)s::vector
            LIMIT %(top_k)s
        """

        with psycopg.connect(self.dsn) as conn:
            rows = conn.execute(sql, params).fetchall()

        citations = []
        for index, row in enumerate(rows, start=1):
            metadata = row[7]
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            citations.append(
                Citation(
                    citation_id=index,
                    chunk_id=row[0],
                    file_id=row[1],
                    filename=row[2],
                    page_start=row[3],
                    page_end=row[4],
                    chunk_index=row[5],
                    content=row[6],
                    metadata=metadata or {},
                    similarity=float(row[8]),
                    vector_similarity=float(row[8]),
                )
            )
        return citations

    def hybrid_search(
        self,
        query_text: str,
        query_embedding: list[float],
        top_k: int,
        client_id: str | None = None,
        file_id: str | None = None,
        semantic_weight: float = 0.65,
        keyword_weight: float = 0.35,
    ) -> list[Citation]:
        import psycopg

        filters = []
        vector_params: dict[str, Any] = {
            "embedding": _to_pgvector(query_embedding),
            "query_text": query_text,
            "candidate_limit": top_k * 4,
            "top_k": top_k,
            "rrf_k": 60.0,
            "semantic_weight": semantic_weight,
            "keyword_weight": keyword_weight,
        }
        if client_id:
            filters.append("client_id = %(client_id)s")
            vector_params["client_id"] = client_id
        if file_id:
            filters.append("file_id = %(file_id)s")
            vector_params["file_id"] = file_id

        filter_clause = ""
        if filters:
            filter_clause = " AND " + " AND ".join(filters)

        sql = f"""
            WITH query AS (
                SELECT websearch_to_tsquery('english', %(query_text)s) AS tsq
            ),
            vector_results AS (
                SELECT
                    chunk_id,
                    chunk_id::text AS chunk_id_text,
                    file_id,
                    filename,
                    page_start,
                    page_end,
                    chunk_index,
                    content,
                    metadata,
                    1 - (embedding <=> %(embedding)s::vector) AS vector_similarity,
                    row_number() OVER (ORDER BY embedding <=> %(embedding)s::vector) AS vector_rank
                FROM chunks
                WHERE embedding IS NOT NULL
                {filter_clause}
                ORDER BY embedding <=> %(embedding)s::vector
                LIMIT %(candidate_limit)s
            ),
            keyword_results AS (
                SELECT
                    chunks.chunk_id,
                    chunks.chunk_id::text AS chunk_id_text,
                    chunks.file_id,
                    chunks.filename,
                    chunks.page_start,
                    chunks.page_end,
                    chunks.chunk_index,
                    chunks.content,
                    chunks.metadata,
                    ts_rank_cd(chunks.content_tsv, query.tsq) AS keyword_score,
                    row_number() OVER (ORDER BY ts_rank_cd(chunks.content_tsv, query.tsq) DESC) AS keyword_rank
                FROM chunks, query
                WHERE chunks.content_tsv @@ query.tsq
                {filter_clause}
                ORDER BY keyword_score DESC
                LIMIT %(candidate_limit)s
            ),
            merged AS (
                SELECT
                    COALESCE(v.chunk_id_text, k.chunk_id_text) AS chunk_id_text,
                    COALESCE(v.file_id, k.file_id) AS file_id,
                    COALESCE(v.filename, k.filename) AS filename,
                    COALESCE(v.page_start, k.page_start) AS page_start,
                    COALESCE(v.page_end, k.page_end) AS page_end,
                    COALESCE(v.chunk_index, k.chunk_index) AS chunk_index,
                    COALESCE(v.content, k.content) AS content,
                    COALESCE(v.metadata, k.metadata) AS metadata,
                    v.vector_similarity,
                    k.keyword_score,
                    (
                        %(semantic_weight)s * COALESCE(1.0 / (%(rrf_k)s + v.vector_rank), 0.0)
                        + %(keyword_weight)s * COALESCE(1.0 / (%(rrf_k)s + k.keyword_rank), 0.0)
                    ) AS hybrid_score
                FROM vector_results v
                FULL OUTER JOIN keyword_results k ON v.chunk_id = k.chunk_id
            )
            SELECT
                chunk_id_text,
                file_id,
                filename,
                page_start,
                page_end,
                chunk_index,
                content,
                metadata,
                vector_similarity,
                keyword_score,
                hybrid_score
            FROM merged
            ORDER BY hybrid_score DESC
            LIMIT %(top_k)s
        """

        with psycopg.connect(self.dsn) as conn:
            rows = conn.execute(sql, vector_params).fetchall()

        citations = []
        for index, row in enumerate(rows, start=1):
            metadata = row[7]
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            vector_similarity = _optional_float(row[8])
            keyword_score = _optional_float(row[9])
            hybrid_score = _optional_float(row[10]) or 0.0
            citations.append(
                Citation(
                    citation_id=index,
                    chunk_id=row[0],
                    file_id=row[1],
                    filename=row[2],
                    page_start=row[3],
                    page_end=row[4],
                    chunk_index=row[5],
                    content=row[6],
                    metadata=metadata or {},
                    similarity=vector_similarity if vector_similarity is not None else hybrid_score,
                    vector_similarity=vector_similarity,
                    keyword_score=keyword_score,
                    hybrid_score=hybrid_score,
                )
            )
        return citations


def build_context(citations: list[Citation]) -> str:
    blocks = []
    for citation in citations:
        page = _page_label(citation.page_start, citation.page_end)
        blocks.append(
            f"[{citation.citation_id}] {citation.filename} {page}\n"
            f"file_id={citation.file_id} chunk_index={citation.chunk_index}\n"
            f"{citation.content}"
        )
    return "\n\n".join(blocks)


def _page_label(page_start: int | None, page_end: int | None) -> str:
    if page_start is None and page_end is None:
        return ""
    if page_start == page_end or page_end is None:
        return f"page {page_start}"
    return f"pages {page_start}-{page_end}"


def _to_pgvector(embedding: list[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in embedding) + "]"


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)
