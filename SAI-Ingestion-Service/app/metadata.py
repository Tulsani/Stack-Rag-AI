from __future__ import annotations

import json
import re

from starlette.datastructures import Headers

from .config import MAX_FILE_SIZE_BYTES, SUPPORTED_MIME_TYPES
from .models import DocumentTag, ParsedUploadRequest, UploadMetadata


class MetadataValidationError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"[{field}] {message}")
        self.field = field


class H:
    CLIENT_ID = "x-doc-client-id"
    USER_ID = "x-doc-user-id"
    FILE_TYPE = "x-doc-file-type"
    FILE_SUB_TYPE = "x-doc-file-sub-type"
    DOC_TYPE = "x-doc-doc-type"
    STAGE = "x-doc-stage"
    PARENT_FOLDER = "x-doc-parent-folder"
    UPLOADED_BY = "x-doc-uploaded-by"
    LINKED = "x-doc-linked"
    DESCRIPTION = "x-doc-description"
    TAGS = "x-doc-tags"
    FILENAME = "x-doc-filename"
    CONTENT_TYPE = "content-type"
    FILE_SIZE = "x-doc-file-size"


def _header(headers: Headers, key: str) -> str:
    return (headers.get(key) or "").strip()


def _require_header(headers: Headers, key: str, field_name: str) -> str:
    value = _header(headers, key)
    if not value:
        raise MetadataValidationError(field_name, f"Header '{key}' is required")
    return value


def _sanitise_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._\-\s]", "", name).strip()


def _parse_tags(raw: str) -> list[DocumentTag]:
    if not raw:
        return []

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MetadataValidationError("tags", "x-doc-tags must be valid JSON") from exc

    if not isinstance(parsed, list):
        raise MetadataValidationError("tags", "x-doc-tags must be a JSON array")

    tags: list[DocumentTag] = []
    for index, tag in enumerate(parsed):
        if not isinstance(tag, dict) or not isinstance(tag.get("key"), str) or not isinstance(tag.get("value"), str):
            raise MetadataValidationError(
                "tags",
                f"tags[{index}] must have string 'key' and 'value' fields",
            )
        tags.append(DocumentTag(key=tag["key"], value=tag["value"]))

    return tags


def parse_request_from_headers(headers: Headers) -> ParsedUploadRequest:
    client_id = _require_header(headers, H.CLIENT_ID, "clientId")
    user_id = _require_header(headers, H.USER_ID, "userId")
    file_type = _require_header(headers, H.FILE_TYPE, "fileType")
    raw_filename = _require_header(headers, H.FILENAME, "filename")
    raw_content_type = _require_header(headers, H.CONTENT_TYPE, "contentType")
    raw_size = _require_header(headers, H.FILE_SIZE, "fileSizeBytes")

    content_type = raw_content_type.split(";")[0].strip().lower()
    if content_type not in SUPPORTED_MIME_TYPES:
        allowed = ", ".join(sorted(SUPPORTED_MIME_TYPES))
        raise MetadataValidationError(
            "contentType",
            f"Unsupported MIME type '{content_type}'. Allowed: {allowed}",
        )

    try:
        file_size_bytes = int(raw_size)
    except ValueError as exc:
        raise MetadataValidationError("fileSizeBytes", "x-doc-file-size must be a positive integer") from exc

    if file_size_bytes <= 0:
        raise MetadataValidationError("fileSizeBytes", "x-doc-file-size must be a positive integer")
    if file_size_bytes > MAX_FILE_SIZE_BYTES:
        raise MetadataValidationError("fileSizeBytes", "File exceeds the 500 MB limit")

    metadata = UploadMetadata(
        clientId=client_id,
        userId=user_id,
        fileType=file_type,
        fileSubType=_header(headers, H.FILE_SUB_TYPE) or None,
        docType=_header(headers, H.DOC_TYPE) or None,
        stage=_header(headers, H.STAGE) or None,
        parentFolder=_header(headers, H.PARENT_FOLDER) or None,
        uploadedBy=_header(headers, H.UPLOADED_BY) or None,
        description=_header(headers, H.DESCRIPTION) or None,
        linked=_header(headers, H.LINKED).lower() == "true",
        tags=_parse_tags(_header(headers, H.TAGS)),
    )

    return ParsedUploadRequest(
        filename=_sanitise_filename(raw_filename),
        content_type=content_type,
        file_size_bytes=file_size_bytes,
        metadata=metadata,
    )
