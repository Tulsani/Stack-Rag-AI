from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class MistralEmbeddingClient:
    def __init__(self, api_key: str, model: str, expected_dimension: int) -> None:
        self.api_key = api_key
        self.model = model
        self.expected_dimension = expected_dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        payload = {
            "model": self.model,
            "input": texts,
        }

        with httpx.Client(timeout=httpx.Timeout(120.0)) as client:
            response = client.post(
                "https://api.mistral.ai/v1/embeddings",
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
                    "Mistral embeddings request failed",
                    extra={
                        "status_code": response.status_code,
                        "model": self.model,
                        "batch_size": len(texts),
                        "response_body": response.text[:1000],
                    },
                )
                raise RuntimeError(
                    f"Mistral embeddings failed with HTTP {response.status_code}: {response.text[:500]}"
                ) from exc
            result = response.json()

        ordered = sorted(result.get("data", []), key=lambda item: item["index"])
        embeddings = [item["embedding"] for item in ordered]
        if len(embeddings) != len(texts):
            raise ValueError(f"Expected {len(texts)} embeddings, got {len(embeddings)}")

        for embedding in embeddings:
            if len(embedding) != self.expected_dimension:
                raise ValueError(
                    f"Expected embedding dimension {self.expected_dimension}, got {len(embedding)}"
                )

        return embeddings
