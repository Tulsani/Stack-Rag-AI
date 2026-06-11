from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import Citation

PII_TAGS = {"pii", "private", "confidential", "personal", "personal_info", "sensitive"}
MEDICAL_TAGS = {"medical", "health", "healthcare", "clinical", "patient"}
LEGAL_TAGS = {"legal", "contract", "nda", "agreement"}


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    answer: str | None = None
    warning: str | None = None


def evaluate_document_policy(citations: list[Citation]) -> PolicyDecision:
    tags = set()
    for citation in citations:
        tags |= _metadata_tag_terms(citation.metadata)

    if tags & PII_TAGS:
        return PolicyDecision(
            allowed=False,
            answer="I cannot answer from documents tagged as PII, private, confidential, or sensitive.",
            warning="pii_or_private_document",
        )

    if tags & MEDICAL_TAGS:
        return PolicyDecision(
            allowed=True,
            warning="Medical/health document: this is a document summary, not medical advice.",
        )

    if tags & LEGAL_TAGS:
        return PolicyDecision(
            allowed=True,
            warning="Legal/contract document: this is a document summary, not legal advice.",
        )

    return PolicyDecision(allowed=True)


def filter_blocked_citations(citations: list[Citation]) -> tuple[list[Citation], list[Citation]]:
    allowed = []
    blocked = []
    for citation in citations:
        if is_blocked_citation(citation):
            blocked.append(citation)
        else:
            allowed.append(citation)
    return allowed, blocked


def is_blocked_citation(citation: Citation) -> bool:
    return bool(_metadata_tag_terms(citation.metadata) & PII_TAGS)


def _metadata_tag_terms(metadata: dict[str, Any]) -> set[str]:
    raw_tags = metadata.get("tags") or metadata.get("tag") or []
    if isinstance(raw_tags, str):
        raw_tags = [{"key": raw_tags, "value": raw_tags}]
    if not isinstance(raw_tags, list):
        return set()

    terms = set()
    for tag in raw_tags:
        if isinstance(tag, dict):
            for value in tag.values():
                terms.add(_normalize(value))
        else:
            terms.add(_normalize(tag))
    return {term for term in terms if term}


def _normalize(value: Any) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")
