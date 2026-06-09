from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class MistralClient:
    def __init__(self, api_key: str, embed_model: str, chat_model: str, embedding_dimension: int) -> None:
        self.api_key = api_key
        self.embed_model = embed_model
        self.chat_model = chat_model
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

    def answer(self, question: str, context: str) -> str:
        payload = {
            "model": self.chat_model,
            "temperature": 0.1,
            "max_tokens": 700,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a retrieval-augmented assistant. "
                        "Answer using only the provided context. "
                        "If the context does not contain enough evidence, "
                        "say exactly: insufficient evidence."
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
