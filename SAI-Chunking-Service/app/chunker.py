from __future__ import annotations

import re
from hashlib import sha256

from .models import Chunk, ExtractedPage

TOKEN_PATTERN = re.compile(r"\S+")
PARAGRAPH_SPLIT_PATTERN = re.compile(r"\n\s*\n+")


def chunk_pages(pages: list[ExtractedPage], target_tokens: int, overlap_tokens: int) -> list[Chunk]:
    if target_tokens <= 0:
        raise ValueError("target_tokens must be greater than zero")
    if overlap_tokens < 0 or overlap_tokens >= target_tokens:
        raise ValueError("overlap_tokens must be non-negative and smaller than target_tokens")

    paragraphs = []
    for page in pages:
        for paragraph in PARAGRAPH_SPLIT_PATTERN.split(page.text):
            text = " ".join(paragraph.split())
            if text:
                paragraphs.append((page.page_number, text))

    chunks: list[Chunk] = []
    current_parts: list[str] = []
    current_pages: list[int] = []
    current_tokens = 0

    for page_number, paragraph in paragraphs:
        paragraph_tokens = _count_tokens(paragraph)
        if current_parts and current_tokens + paragraph_tokens > target_tokens:
            chunks.append(_build_chunk(len(chunks), current_parts, current_pages, current_tokens))
            current_parts, current_pages, current_tokens = _overlap_seed(chunks[-1].text, overlap_tokens)

        if paragraph_tokens > target_tokens:
            for slice_text in _slice_words(paragraph, target_tokens):
                if current_parts:
                    chunks.append(_build_chunk(len(chunks), current_parts, current_pages, current_tokens))
                    current_parts, current_pages, current_tokens = _overlap_seed(chunks[-1].text, overlap_tokens)
                current_parts.append(slice_text)
                current_pages.append(page_number)
                current_tokens = _count_tokens(slice_text)
        else:
            current_parts.append(paragraph)
            current_pages.append(page_number)
            current_tokens += paragraph_tokens

    if current_parts:
        chunks.append(_build_chunk(len(chunks), current_parts, current_pages, current_tokens))

    return chunks


def _build_chunk(index: int, parts: list[str], pages: list[int], token_count: int) -> Chunk:
    text = "\n\n".join(parts).strip()
    digest = sha256(text.encode("utf-8")).hexdigest()[:16]
    return Chunk(
        chunk_id=f"chunk_{index:05d}_{digest}",
        index=index,
        text=text,
        page_start=min(pages) if pages else None,
        page_end=max(pages) if pages else None,
        token_count_estimate=token_count,
    )


def _overlap_seed(text: str, overlap_tokens: int) -> tuple[list[str], list[int], int]:
    if overlap_tokens == 0:
        return [], [], 0
    words = TOKEN_PATTERN.findall(text)
    overlap = " ".join(words[-overlap_tokens:])
    return ([overlap] if overlap else []), [], _count_tokens(overlap)


def _slice_words(text: str, max_tokens: int) -> list[str]:
    words = TOKEN_PATTERN.findall(text)
    return [" ".join(words[i : i + max_tokens]) for i in range(0, len(words), max_tokens)]


def _count_tokens(text: str) -> int:
    return len(TOKEN_PATTERN.findall(text))
