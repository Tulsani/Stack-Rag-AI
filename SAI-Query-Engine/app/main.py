from __future__ import annotations

import logging
import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException

from .config import Settings
from .mistral_client import MistralClient
from .models import HealthResponse, HybridQueryRequest, QueryRequest, QueryResponse
from .retrieval import ChunkRetriever
from .service import QueryService

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SAI Query Engine",
    version="0.1.0",
    description="FastAPI query endpoint for the Stack AI RAG pipeline.",
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    try:
        return get_query_service().answer(request)
    except Exception as exc:
        logger.exception("Query failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/query/hybrid", response_model=QueryResponse)
def hybrid_query(request: HybridQueryRequest) -> QueryResponse:
    try:
        return get_query_service().hybrid_answer(request)
    except Exception as exc:
        logger.exception("Hybrid query failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@lru_cache(maxsize=1)
def get_query_service() -> QueryService:
    settings = Settings.from_env()
    mistral = MistralClient(
        api_key=settings.mistral_api_key,
        embed_model=settings.mistral_embed_model,
        chat_model=settings.mistral_chat_model,
        embedding_dimension=settings.embedding_dimension,
    )
    retriever = ChunkRetriever(settings.postgres_dsn)
    return QueryService(
        mistral=mistral,
        retriever=retriever,
        default_top_k=settings.default_top_k,
        default_min_similarity=settings.min_similarity,
    )
