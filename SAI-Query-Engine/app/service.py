from __future__ import annotations

from .mistral_client import MistralClient
from .models import HybridQueryRequest, QueryRequest, QueryResponse
from .retrieval import ChunkRetriever, build_context

GREETING_QUERIES = {
    "hi",
    "hello",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
}


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

    def answer(self, request: QueryRequest) -> QueryResponse:
        question = request.question.strip()
        if _is_greeting(question):
            return QueryResponse(
                answer="Hello. Ask a question about the uploaded knowledge base and I can search it.",
                used_retrieval=False,
                insufficient_evidence=False,
                citations=[],
            )

        top_k = request.top_k or self.default_top_k
        min_similarity = request.min_similarity
        if min_similarity is None:
            min_similarity = self.default_min_similarity

        query_embedding = self.mistral.embed_query(question)
        citations = self.retriever.search(
            query_embedding=query_embedding,
            top_k=top_k,
            client_id=request.client_id,
            file_id=request.file_id,
        )

        usable_citations = [citation for citation in citations if citation.similarity >= min_similarity]
        if not usable_citations:
            return QueryResponse(
                answer="insufficient evidence",
                used_retrieval=True,
                insufficient_evidence=True,
                citations=citations,
            )

        answer = self.mistral.answer(question=question, context=build_context(usable_citations))
        insufficient = answer.strip().lower() == "insufficient evidence"
        return QueryResponse(
            answer=answer,
            used_retrieval=True,
            insufficient_evidence=insufficient,
            citations=usable_citations,
        )

    def hybrid_answer(self, request: HybridQueryRequest) -> QueryResponse:
        question = request.question.strip()
        if _is_greeting(question):
            return QueryResponse(
                answer="Hello. Ask a question about the uploaded knowledge base and I can search it.",
                used_retrieval=False,
                insufficient_evidence=False,
                citations=[],
            )

        top_k = request.top_k or self.default_top_k
        min_similarity = request.min_similarity
        if min_similarity is None:
            min_similarity = self.default_min_similarity

        query_embedding = self.mistral.embed_query(question)
        citations = self.retriever.hybrid_search(
            query_text=question,
            query_embedding=query_embedding,
            top_k=top_k,
            client_id=request.client_id,
            file_id=request.file_id,
            semantic_weight=request.semantic_weight,
            keyword_weight=request.keyword_weight,
        )

        usable_citations = [
            citation
            for citation in citations
            if citation.vector_similarity is None or citation.vector_similarity >= min_similarity
        ]
        if not usable_citations:
            return QueryResponse(
                answer="insufficient evidence",
                used_retrieval=True,
                insufficient_evidence=True,
                citations=citations,
            )

        answer = self.mistral.answer(question=question, context=build_context(usable_citations))
        insufficient = answer.strip().lower() == "insufficient evidence"
        return QueryResponse(
            answer=answer,
            used_retrieval=True,
            insufficient_evidence=insufficient,
            citations=usable_citations,
        )


def _is_greeting(question: str) -> bool:
    normalized = question.lower().strip(" .!?")
    return normalized in GREETING_QUERIES
