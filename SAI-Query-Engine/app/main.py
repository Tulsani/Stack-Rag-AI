from __future__ import annotations

import logging
import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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

cors_origins = os.getenv("CORS_ORIGINS") or os.getenv("CORS_ORIGIN") or "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins.split(",") if origin.strip()],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path in {"/health"}:
        return await call_next(request)

    if request.headers.get("x-api-key-header") != get_settings().api_key:
        return JSONResponse(status_code=403, content={"detail": "Invalid API key"})

    return await call_next(request)


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
def get_settings() -> Settings:
    return Settings.from_env()


@lru_cache(maxsize=1)
def get_query_service() -> QueryService:
    settings = get_settings()
    mistral = MistralClient(
        api_key=settings.mistral_api_key,
        embed_model=settings.mistral_embed_model,
        chat_model=settings.mistral_chat_model,
        query_rewrite_model=settings.mistral_query_rewrite_model,
        embedding_dimension=settings.embedding_dimension,
    )
    retriever = ChunkRetriever(settings.postgres_dsn)
    return QueryService(
        mistral=mistral,
        retriever=retriever,
        default_top_k=settings.default_top_k,
        default_min_similarity=settings.min_similarity,
    )
