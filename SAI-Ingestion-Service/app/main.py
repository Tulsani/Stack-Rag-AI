from __future__ import annotations

import logging
import os
import time
from functools import lru_cache
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .aws_io import AwsIngestionStore, FileRecordConflictError
from .config import MIME_TO_EXTENSION, Settings
from .metadata import MetadataValidationError, parse_request_from_headers
from .models import UploadInitResponse

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SAI Ingestion Service",
    version="0.1.0",
    description="FastAPI pre-signed upload URL issuer for the Stack AI RAG pipeline.",
)

settings = Settings.from_env()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ingestion/health")
def ingestion_health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingestion/upload", response_model=UploadInitResponse)
def create_upload(request: Request) -> JSONResponse | dict[str, object]:
    try:
        parsed = parse_request_from_headers(request.headers)
    except MetadataValidationError as exc:
        logger.warning("Validation error", extra={"field": exc.field})
        return JSONResponse(status_code=400, content={"error": str(exc)})

    file_id = str(uuid4())
    now = str(int(time.time() * 1000))
    extension = MIME_TO_EXTENSION[parsed.content_type]
    metadata = parsed.metadata

    try:
        presign = get_store().generate_presigned_put_url(
            file_id=file_id,
            content_type=parsed.content_type,
            metadata=metadata,
        )
    except Exception as exc:
        logger.exception("Failed to generate presigned URL", extra={"file_id": file_id})
        return JSONResponse(status_code=500, content={"error": "Could not generate upload URL"})

    record = {
        "fileId": file_id,
        "clientId": metadata.client_id,
        "userId": metadata.user_id,
        "fileType": metadata.file_type,
        "fileSubType": metadata.file_sub_type or "",
        "docType": metadata.doc_type or "",
        "stage": metadata.stage or "",
        "uploadedBy": metadata.uploaded_by or "",
        "parentFolder": metadata.parent_folder or "",
        "description": metadata.description or "",
        "tags": [tag.model_dump() for tag in metadata.tags],
        "linked": metadata.linked,
        "fileName": parsed.filename,
        "mimeType": parsed.content_type,
        "extension": extension,
        "fileSize": str(parsed.file_size_bytes),
        "s3Key": presign["s3Key"],
        "s3Bucket": settings.upload_bucket,
        "uploadStatus": "PENDING",
        "createdAt": now,
        "lastUpdatedAt": now,
    }
    record["searchString"] = build_search_string(record)

    try:
        get_store().persist_file_record(record)
    except FileRecordConflictError:
        logger.exception("Generated duplicate fileId", extra={"file_id": file_id})
        return JSONResponse(status_code=409, content={"error": "File record already exists"})
    except Exception:
        logger.exception("DynamoDB write failed", extra={"file_id": file_id})
        return JSONResponse(status_code=500, content={"error": "Could not register file record"})

    logger.info(
        "Presigned URL issued",
        extra={
            "file_id": file_id,
            "client_id": metadata.client_id,
            "user_id": metadata.user_id,
            "s3_key": presign["s3Key"],
            "mime_type": parsed.content_type,
            "size_bytes": parsed.file_size_bytes,
        },
    )

    return {
        "fileId": file_id,
        "uploadUrl": presign["uploadUrl"],
        "s3Key": presign["s3Key"],
        "expiresIn": presign["expiresIn"],
        "metadata": record,
    }


def build_search_string(record: dict[str, object]) -> str:
    tags = record.get("tags") if isinstance(record.get("tags"), list) else []
    tag_values = [
        f"{tag.get('key')}:{tag.get('value')}"
        for tag in tags
        if isinstance(tag, dict) and tag.get("key") and tag.get("value")
    ]
    values = [
        record.get("fileType"),
        record.get("fileSubType"),
        record.get("docType"),
        record.get("fileName"),
        record.get("stage"),
        record.get("clientId"),
        record.get("prospectId"),
        record.get("bankerId"),
        *tag_values,
    ]
    return "-".join(str(value) for value in values if value).lower()


@lru_cache(maxsize=1)
def get_store() -> AwsIngestionStore:
    return AwsIngestionStore(
        upload_bucket=settings.upload_bucket,
        documents_table=settings.documents_table,
        presign_expiry_seconds=settings.presign_expiry_seconds,
    )
