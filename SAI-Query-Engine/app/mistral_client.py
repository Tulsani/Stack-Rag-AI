from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from .models import QueryPlan

logger = logging.getLogger(__name__)


class MistralClient:
    def __init__(
        self,
        api_key: str,
        embed_model: str,
        chat_model: str,
        query_rewrite_model: str,
        embedding_dimension: int,
    ) -> None:
        self.api_key = api_key
        self.embed_model = embed_model
        self.chat_model = chat_model
        self.query_rewrite_model = query_rewrite_model
        self.embedding_dimension = embedding_dimension

    def embed_query(self, query: str) -> list[float]:
        payload = {
            "model": self.embed_model,
            "input": [query],
        }
        result = self._post("https://api.mistral.ai/v1/embeddings", payload)
        data = result.get("data") or []
        if not data:
            raise ValueError("Mistral returned no query embedding")

        embedding = data[0]["embedding"]
        if len(embedding) != self.embedding_dimension:
            raise ValueError(
                f"Expected embedding dimension {self.embedding_dimension}, got {len(embedding)}"
            )
        return embedding

    def answer(self, question: str, context: str, answer_style: str = "factual") -> str:
        payload = {
            "model": self.chat_model,
            "temperature": 0.1,
            "max_tokens": 700,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a retrieval-augmented assistant. Answer using only the provided context. "
                        "Cite sources inline as [1], [2], etc. If the context does not contain enough "
                        "evidence, say exactly: insufficient evidence. "
                        f"Use this answer style when possible: {answer_style}."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Question:\n{question}\n\nContext:\n{context}",
                },
            ],
        }
        result = self._post("https://api.mistral.ai/v1/chat/completions", payload)
        return _message_content_to_text(result["choices"][0]["message"]["content"]).strip()

    def plan_query(self, question: str, max_rewrites: int) -> QueryPlan:
        payload = {
            "model": self.query_rewrite_model,
            "temperature": 0.1,
            "max_tokens": 400,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a query planner for a document RAG system. Decide whether the user "
                        "question requires searching uploaded documents. Return only JSON with this shape: "
                        "{\"intent\":\"greeting|capability_question|knowledge_base_question|summary_request|"
                        "comparison_request|out_of_scope|unsafe_or_sensitive\","
                        "\"should_search\":true,"
                        "\"direct_answer\":null,"
                        "\"rewritten_queries\":[\"query one\"],"
                        "\"answer_style\":\"factual|summary|list|table|comparison|conversational\"}.\n"
                        "Rules: should_search=false for greetings, small talk, capability questions, "
                        "unrelated general knowledge, or unsafe/sensitive requests. should_search=true only "
                        "when the user asks about uploaded documents or likely document contents. Generate up "
                        "to the requested number of concise retrieval queries. Do not answer knowledge-base "
                        "questions directly."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question: {question}\n"
                        f"Generate up to {max_rewrites} rewritten retrieval queries."
                    ),
                },
            ],
        }
        result = self._post("https://api.mistral.ai/v1/chat/completions", payload)
        content = _message_content_to_text(result["choices"][0]["message"]["content"])
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Mistral query planner returned non-JSON content: {content[:500]}") from exc

        plan = QueryPlan.model_validate(parsed)
        plan.rewritten_queries = _clean_rewrites(question, plan.rewritten_queries, max_rewrites)
        if not plan.direct_answer and not plan.should_search:
            plan.direct_answer = "I can help answer questions about the uploaded knowledge base."
        return plan

    def rewrite_queries(self, question: str, max_rewrites: int) -> list[str]:
        if max_rewrites <= 0:
            return []

        payload = {
            "model": self.query_rewrite_model,
            "temperature": 0.2,
            "max_tokens": 250,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Rewrite user questions into concise retrieval queries for a document RAG system. "
                        "Generate diverse keyword-rich paraphrases with synonyms and domain terms. "
                        "Do not answer the question. Return only JSON in this shape: "
                        "{\"queries\":[\"query one\",\"query two\"]}."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question: {question}\n"
                        f"Return up to {max_rewrites} rewritten search queries."
                    ),
                },
            ],
        }
        result = self._post("https://api.mistral.ai/v1/chat/completions", payload)
        content = _message_content_to_text(result["choices"][0]["message"]["content"])
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Mistral query rewrite returned non-JSON content", extra={"content": content[:500]})
            return []

        queries = parsed.get("queries") or []
        if not isinstance(queries, list):
            return []

        return _clean_rewrites(question, queries, max_rewrites)

    def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=httpx.Timeout(120.0)) as client:
            response = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=payload,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "Mistral request failed",
                    extra={
                        "url": url,
                        "status_code": response.status_code,
                        "response_body": response.text[:1000],
                    },
                )
                raise RuntimeError(
                    f"Mistral request failed with HTTP {response.status_code}: {response.text[:500]}"
                ) from exc
            return response.json()


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "".join(parts)
    return str(content)


def _clean_rewrites(question: str, queries: Any, max_rewrites: int) -> list[str]:
    if not isinstance(queries, list):
        return []

    seen = {question.strip().lower()}
    rewrites = []
    for query in queries:
        if not isinstance(query, str):
            continue
        cleaned = " ".join(query.split())
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        rewrites.append(cleaned)
        if len(rewrites) >= max_rewrites:
            break
    return rewrites
