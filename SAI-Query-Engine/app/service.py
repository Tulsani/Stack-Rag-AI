from __future__ import annotations

from .mistral_client import MistralClient
from .retrieval import ChunkRetriever, build_context


class QueryService:
    def __init__(
        self,
        mistral: MistralClient,
        retriever: ChunkRetriever,
        default_top_k: int,
        default_min_similarity: float,
    ) -> None:
        self.mistral = mistral
        self.retriever = retriever
        self.default_top_k = default_top_k
        self.default_min_similarity = default_min_similarity

    def answer(self, request: dict) -> dict:
        question = request["question"].strip()

        top_k = request.get("top_k") or self.default_top_k
        min_similarity = request.get("min_similarity")
        if min_similarity is None:
            min_similarity = self.default_min_similarity

        citations = self.retriever.search(
            query_embedding=self.mistral.embed_query(question),
            top_k=top_k,
            client_id=request.get("client_id"),
            file_id=request.get("file_id"),
        )

        usable_citations = [
            citation
            for citation in citations
            if citation["similarity"] >= min_similarity
        ]

        if not usable_citations:
            return {
                "answer": "insufficient evidence",
                "used_retrieval": True,
                "insufficient_evidence": True,
                "citations": citations,
            }

        answer = self.mistral.answer(
            question=question,
            context=build_context(usable_citations),
        )

        return {
            "answer": answer,
            "used_retrieval": True,
            "insufficient_evidence": answer.strip().lower() == "insufficient evidence",
            "citations": usable_citations,
        }