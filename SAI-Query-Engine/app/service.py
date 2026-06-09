from __future__ import annotations

from .mistral_client import MistralClient
from .retrieval import ChunkRetriever, build_context


class QueryService:
    def __init__(
        self,
        mistral: MistralClient,
        retriever: ChunkRetriever,
        top_k: int,
    ) -> None:
        self.mistral = mistral
        self.retriever = retriever
        self.top_k = top_k

    def answer(self, question: str) -> dict:
        embedding = self.mistral.embed_query(question)

        chunks = self.retriever.search(
            query_embedding=embedding,
            top_k=self.top_k,
        )

        context = build_context(chunks)

        answer = self.mistral.answer(
            question=question,
            context=context,
        )

        return {
            "answer": answer
        }