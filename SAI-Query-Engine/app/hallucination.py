from __future__ import annotations

import re
from dataclasses import dataclass

SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")
CITATION_PATTERN = re.compile(r"\[(\d+)\]")
TAG_PATTERN = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class HallucinationCheck:
    supported: bool
    unsupported_claims: list[str]


def check_answer_citations(answer: str, valid_citation_ids: set[int]) -> HallucinationCheck:
    plain = TAG_PATTERN.sub(" ", answer)
    sentences = [sentence.strip() for sentence in SENTENCE_PATTERN.split(plain) if sentence.strip()]

    unsupported = []
    for sentence in sentences:
        if _skip_sentence(sentence):
            continue

        cited_ids = {int(match) for match in CITATION_PATTERN.findall(sentence)}
        if not cited_ids or not cited_ids & valid_citation_ids:
            unsupported.append(sentence)

    return HallucinationCheck(
        supported=not unsupported,
        unsupported_claims=unsupported,
    )


def _skip_sentence(sentence: str) -> bool:
    lowered = sentence.lower().strip()
    return (
        len(sentence.split()) < 5
        or lowered == "insufficient evidence"
        or lowered.startswith("based on the provided context")
        or lowered.startswith("here is")
        or lowered.startswith("here are")
    )
