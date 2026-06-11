from __future__ import annotations

from pathlib import PurePosixPath

from .models import ChunkRecord, JsonDict


def parse_chunk_payload(payload: JsonDict) -> list[ChunkRecord]:
    source = payload.get("source") or {}
    source_metadata = source.get("metadata") or {}
    first_chunk_metadata = _first_chunk_metadata(payload)
    filename = _filename_from_source(source)
    file_id = (
        payload.get("fileId")
        or source_metadata.get("file-id")
        or first_chunk_metadata.get("fileId")
        or _file_id_from_artifact(payload)
        or _stem(filename)
    )

    if not file_id:
        raise ValueError("Chunk payload is missing fileId")

    records = []
    for chunk in payload.get("chunks", []):
        chunk_metadata = chunk.get("metadata") or {}
        content = (chunk.get("text") or "").strip()
        if not content:
            continue

        records.append(
            ChunkRecord(
                file_id=file_id,
                filename=filename,
                client_id=chunk_metadata.get("clientId") or source_metadata.get("client-id"),
                user_id=chunk_metadata.get("userId") or source_metadata.get("user-id"),
                file_type=chunk_metadata.get("fileType") or source_metadata.get("file-type"),
                file_sub_type=chunk_metadata.get("fileSubType") or source_metadata.get("file-sub-type"),
                doc_type=chunk_metadata.get("docType") or source_metadata.get("doc-type"),
                stage=chunk_metadata.get("stage") or source_metadata.get("stage"),
                page_start=chunk.get("pageStart"),
                page_end=chunk.get("pageEnd"),
                chunk_index=int(chunk["index"]),
                content=content,
                metadata={
                    **chunk_metadata,
                    "chunkId": chunk.get("chunkId"),
                    "sourceBucket": source.get("bucket"),
                    "sourceKey": source.get("key"),
                    "chunkArtifact": payload.get("chunkArtifact"),
                    "tokenCountEstimate": chunk.get("tokenCountEstimate"),
                    "schemaVersion": payload.get("schemaVersion"),
                },
            )
        )
    return records


def _first_chunk_metadata(payload: JsonDict) -> JsonDict:
    for chunk in payload.get("chunks", []):
        metadata = chunk.get("metadata")
        if isinstance(metadata, dict):
            return metadata
    return {}


def _filename_from_source(source: JsonDict) -> str:
    raw = source.get("key") or source.get("fileName") or source.get("absolutePath") or "unknown"
    return PurePosixPath(raw).name


def _file_id_from_artifact(payload: JsonDict) -> str | None:
    artifact = payload.get("chunkArtifact") or {}
    key = artifact.get("key")
    if not key:
        return None
    parts = PurePosixPath(key).parts
    if len(parts) >= 2:
        return parts[-2]
    return None


def _stem(filename: str) -> str | None:
    if not filename or filename == "unknown":
        return None
    return PurePosixPath(filename).stem
