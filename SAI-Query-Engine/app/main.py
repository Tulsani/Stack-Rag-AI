from __future__ import annotations

import logging
import os

from typing import Any

from fastapi import FastAPI, HTTPException

from .mistral_client import MistralClient
from .retrieval import ChunkRetriever
from .service import QueryService


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SAI Query Engine",
    version="0.1.0",
    description="FastAPI query endpoint for the Stack AI RAG pipeline.",
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query")
def query(request: dict[str, Any]):
    try:
        question = request["question"]
        return get_query_service().answer(question)
    except Exception as exc:
        logger.exception("Query failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def get_query_service():
    mistral = MistralClient(
        api_key=os.environ["MISTRAL_API_KEY"],
        embed_model=os.getenv("MISTRAL_EMBED_MODEL", "mistral-embed"),
        chat_model=os.getenv("MISTRAL_CHAT_MODEL", "mistral-small-latest"),
        embedding_dimension=int(os.getenv("EMBEDDING_DIMENSION", "1024")),
    )

    retriever = ChunkRetriever(os.environ["POSTGRES_DSN"])

    return QueryService(
        mistral=mistral,
        retriever=retriever,
        top_k=int(os.getenv("DEFAULT_TOP_K", "5")),
    )