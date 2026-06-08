from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChunkArtifactRef:
    bucket: str
    key: str
    file_id: str | None = None


@dataclass(frozen=True)
class ChunkRecord:
    file_id: str
    filename: str
    client_id: str | None
    user_id: str | None
    file_type: str | None
    file_sub_type: str | None
    doc_type: str | None
    stage: str | None
    page_start: int | None
    page_end: int | None
    chunk_index: int
    content: str
    metadata: dict[str, Any]


JsonDict = dict[str, Any]
