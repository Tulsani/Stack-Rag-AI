from __future__ import annotations

import logging

from .mistral_client import MistralClient
from .models import Citation, HybridQueryRequest, QueryPlan, QueryRequest, QueryResponse
from .retrieval import ChunkRetriever, build_context

logger = logging.getLogger(__name__)

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
        plan = self._plan_query(question, request)
        if not plan.should_search:
            return QueryResponse(
                answer=plan.direct_answer or "I can help answer questions about the uploaded knowledge base.",
                used_retrieval=False,
                insufficient_evidence=False,
                citations=[],
                rewritten_queries=plan.rewritten_queries,
                intent=plan.intent,
                answer_style=plan.answer_style,
            )

        top_k = request.top_k or self.default_top_k
        min_similarity = request.min_similarity
        if min_similarity is None:
            min_similarity = self.default_min_similarity

        rewritten_queries = plan.rewritten_queries if request.use_query_rewrite else []
        retrieval_queries = [question, *rewritten_queries]
        citation_lists = []
        for retrieval_query in retrieval_queries:
            query_embedding = self.mistral.embed_query(retrieval_query)
            citation_lists.append(
                self.retriever.search(
                    query_embedding=query_embedding,
                    top_k=top_k,
                    client_id=request.client_id,
                    file_id=request.file_id,
                )
            )
        citations = _merge_citation_lists(citation_lists, top_k)

        usable_citations = [citation for citation in citations if citation.similarity >= min_similarity]
        if not usable_citations:
            return QueryResponse(
                answer="insufficient evidence",
                used_retrieval=True,
                insufficient_evidence=True,
                citations=citations,
                rewritten_queries=rewritten_queries,
                intent=plan.intent,
                answer_style=plan.answer_style,
            )

        answer = self.mistral.answer(
            question=question,
            context=build_context(usable_citations),
            answer_style=plan.answer_style,
        )
        insufficient = answer.strip().lower() == "insufficient evidence"
        return QueryResponse(
            answer=answer,
            used_retrieval=True,
            insufficient_evidence=insufficient,
            citations=usable_citations,
            rewritten_queries=rewritten_queries,
            intent=plan.intent,
            answer_style=plan.answer_style,
        )

    def hybrid_answer(self, request: HybridQueryRequest) -> QueryResponse:
        question = request.question.strip()
        plan = self._plan_query(question, request)
        if not plan.should_search:
            return QueryResponse(
                answer=plan.direct_answer or "I can help answer questions about the uploaded knowledge base.",
                used_retrieval=False,
                insufficient_evidence=False,
                citations=[],
                rewritten_queries=plan.rewritten_queries,
                intent=plan.intent,
                answer_style=plan.answer_style,
            )

        top_k = request.top_k or self.default_top_k
        min_similarity = request.min_similarity
        if min_similarity is None:
            min_similarity = self.default_min_similarity

        rewritten_queries = plan.rewritten_queries if request.use_query_rewrite else []
        retrieval_queries = [question, *rewritten_queries]
        citation_lists = []
        for retrieval_query in retrieval_queries:
            query_embedding = self.mistral.embed_query(retrieval_query)
            citation_lists.append(
                self.retriever.hybrid_search(
                    query_text=retrieval_query,
                    query_embedding=query_embedding,
                    top_k=top_k,
                    client_id=request.client_id,
                    file_id=request.file_id,
                    semantic_weight=request.semantic_weight,
                    keyword_weight=request.keyword_weight,
                )
            )
        citations = _merge_citation_lists(citation_lists, top_k)

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
                rewritten_queries=rewritten_queries,
                intent=plan.intent,
                answer_style=plan.answer_style,
            )

        answer = self.mistral.answer(
            question=question,
            context=build_context(usable_citations),
            answer_style=plan.answer_style,
        )
        insufficient = answer.strip().lower() == "insufficient evidence"
        return QueryResponse(
            answer=answer,
            used_retrieval=True,
            insufficient_evidence=insufficient,
            citations=usable_citations,
            rewritten_queries=rewritten_queries,
            intent=plan.intent,
            answer_style=plan.answer_style,
        )

    def _plan_query(self, question: str, request: QueryRequest) -> QueryPlan:
        if not request.use_query_planner:
            return QueryPlan(
                intent="greeting" if _is_greeting(question) else "knowledge_base_question",
                should_search=not _is_greeting(question),
                direct_answer="Hello. Ask a question about the uploaded knowledge base and I can search it."
                if _is_greeting(question)
                else None,
                rewritten_queries=self._rewrite_queries(question, request.use_query_rewrite, request.max_rewrites),
                answer_style="conversational" if _is_greeting(question) else "factual",
            )

        try:
            plan = self.mistral.plan_query(question, request.max_rewrites if request.use_query_rewrite else 0)
        except Exception:
            logger.exception("Query planning failed; falling back to local greeting check and rewrite")
            return QueryPlan(
                intent="greeting" if _is_greeting(question) else "knowledge_base_question",
                should_search=not _is_greeting(question),
                direct_answer="Hello. Ask a question about the uploaded knowledge base and I can search it."
                if _is_greeting(question)
                else None,
                rewritten_queries=self._rewrite_queries(question, request.use_query_rewrite, request.max_rewrites),
                answer_style="conversational" if _is_greeting(question) else "factual",
            )

        if not request.use_query_rewrite:
            plan.rewritten_queries = []
        return plan

    def _rewrite_queries(self, question: str, enabled: bool, max_rewrites: int) -> list[str]:
        if not enabled or max_rewrites <= 0:
            return []
        try:
            return self.mistral.rewrite_queries(question, max_rewrites)
        except Exception:
            logger.exception("Query rewrite failed; continuing with original query only")
            return []


def _is_greeting(question: str) -> bool:
    normalized = question.lower().strip(" .!?")
    return normalized in GREETING_QUERIES


def _merge_citation_lists(citation_lists: list[list[Citation]], top_k: int) -> list[Citation]:
    by_chunk_id: dict[str, Citation] = {}

    for citations in citation_lists:
        for citation in citations:
            chunk_id = citation.chunk_id
            existing = by_chunk_id.get(chunk_id)
            if existing is None or _primary_score(citation) > _primary_score(existing):
                by_chunk_id[chunk_id] = citation

    ranked = sorted(by_chunk_id.values(), key=_primary_score, reverse=True)
    return [
        citation.model_copy(update={"citation_id": index})
        for index, citation in enumerate(ranked[:top_k], start=1)
    ]


def _primary_score(citation: Citation) -> float:
    if citation.hybrid_score is not None:
        return citation.hybrid_score
    if citation.vector_similarity is not None:
        return citation.vector_similarity
    return citation.similarity
