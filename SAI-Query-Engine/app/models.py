from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    client_id: str | None = None
    file_id: str | None = None
    min_similarity: float | None = Field(default=None, ge=0.0, le=1.0)


class Citation(BaseModel):
    citation_id: int
    chunk_id: str
    file_id: str
    filename: str
    page_start: int | None
    page_end: int | None
    chunk_index: int
    similarity: float
    content: str
    metadata: dict[str, Any]


class QueryResponse(BaseModel):
    answer: str
    used_retrieval: bool
    insufficient_evidence: bool
    citations: list[Citation]


class HealthResponse(BaseModel):
    status: str
