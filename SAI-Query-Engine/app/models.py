from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    client_id: str | None = None
    file_id: str | None = None
    min_similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    use_query_planner: bool = True
    use_query_rewrite: bool = True
    max_rewrites: int = Field(default=3, ge=0, le=3)


class HybridQueryRequest(QueryRequest):
    semantic_weight: float = Field(default=0.65, ge=0.0, le=1.0)
    keyword_weight: float = Field(default=0.35, ge=0.0, le=1.0)


class Citation(BaseModel):
    citation_id: int
    chunk_id: str
    file_id: str
    filename: str
    page_start: int | None
    page_end: int | None
    chunk_index: int
    similarity: float
    vector_similarity: float | None = None
    keyword_score: float | None = None
    hybrid_score: float | None = None
    content: str
    metadata: dict[str, Any]


class QueryResponse(BaseModel):
    answer: str
    used_retrieval: bool
    insufficient_evidence: bool
    citations: list[Citation]
    rewritten_queries: list[str] = Field(default_factory=list)
    intent: str | None = None
    answer_style: str | None = None
    policy_warning: str | None = None
    hallucination_warning: str | None = None
    unsupported_claims: list[str] = Field(default_factory=list)


class QueryPlan(BaseModel):
    intent: str = "knowledge_base_question"
    should_search: bool = True
    direct_answer: str | None = None
    rewritten_queries: list[str] = Field(default_factory=list)
    answer_style: str = "factual"


class HealthResponse(BaseModel):
    status: str
