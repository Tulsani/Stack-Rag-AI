from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class S3Document:
    bucket: str
    key: str
    etag: str | None
    sequencer: str | None


@dataclass(frozen=True)
class StoredDocument:
    bucket: str
    key: str
    body: bytes
    content_type: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str
    confidence: float | None = None


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    index: int
    text: str
    page_start: int | None
    page_end: int | None
    token_count_estimate: int


JsonDict = dict[str, Any]
