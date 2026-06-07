from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone

from app.aws_io import AwsIO, s3_documents_from_sqs_body
from app.chunker import chunk_pages
from app.config import Settings
from app.mistral_ocr import MistralOcrClient, extract_plain_text, should_use_ocr
from app.models import Chunk, ExtractedPage, S3Document, StoredDocument

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)
shutdown_requested = False


def main() -> int:
    settings = Settings.from_env()
    aws = AwsIO(region_name=settings.aws_region)
    ocr = MistralOcrClient(api_key=settings.mistral_api_key, model=settings.mistral_ocr_model)

    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    logger.info("Chunking worker started")
    while not shutdown_requested:
        messages = aws.receive_messages(
            queue_url=settings.queue_url,
            wait_time_seconds=settings.sqs_wait_time_seconds,
            visibility_timeout_seconds=settings.sqs_visibility_timeout_seconds,
        )
        if not messages:
            continue

        for message in messages:
            if shutdown_requested:
                break

            receipt_handle = message["ReceiptHandle"]
            try:
                process_message(settings, aws, ocr, message["Body"])
            except Exception:
                logger.exception("Message processing failed; leaving message for retry")
            else:
                aws.delete_message(settings.queue_url, receipt_handle)

    logger.info("Chunking worker stopped")
    return 0


def process_message(settings: Settings, aws: AwsIO, ocr: MistralOcrClient, body: str) -> None:
    docs = s3_documents_from_sqs_body(body)
    if not docs:
        logger.warning("SQS message did not contain S3 records")
        return

    for doc in docs:
        started = time.monotonic()
        stored = aws.fetch_document(doc)
        pages = extract_document_pages(ocr, stored)
        chunks = chunk_pages(
            pages,
            target_tokens=settings.chunk_target_tokens,
            overlap_tokens=settings.chunk_overlap_tokens,
        )
        output_key = build_output_key(stored)
        payload = build_chunk_payload(doc, stored, pages, chunks, settings.output_bucket, output_key)

        aws.write_json(settings.output_bucket, output_key, payload)
        completion = build_completion_payload(settings.output_bucket, output_key, payload)
        aws.publish_completion(settings.completion_topic_arn, completion)

        logger.info(
            "Chunked document",
            extra={
                "source_bucket": doc.bucket,
                "source_key": doc.key,
                "output_key": output_key,
                "chunk_count": len(chunks),
                "duration_seconds": round(time.monotonic() - started, 3),
            },
        )


def extract_document_pages(ocr: MistralOcrClient, document: StoredDocument) -> list[ExtractedPage]:
    pages = ocr.extract_pages(document) if should_use_ocr(document) else extract_plain_text(document)
    if not pages:
        raise ValueError(f"No text extracted from s3://{document.bucket}/{document.key}")
    return pages


def build_output_key(document: StoredDocument) -> str:
    file_id = document.metadata.get("file-id") or _safe_stem(document.key)
    client_id = document.metadata.get("client-id") or "unknown-client"
    return f"{client_id}/{file_id}/chunks.json"


def build_chunk_payload(
    s3_event: S3Document,
    document: StoredDocument,
    pages: list[ExtractedPage],
    chunks: list[Chunk],
    output_bucket: str,
    output_key: str,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    file_id = document.metadata.get("file-id") or _safe_stem(document.key)

    return {
        "schemaVersion": "2024-08-01",
        "fileId": file_id,
        "source": {
            "bucket": document.bucket,
            "key": document.key,
            "contentType": document.content_type,
            "etag": s3_event.etag,
            "sequencer": s3_event.sequencer,
            "metadata": document.metadata,
        },
        "chunkArtifact": {
            "bucket": output_bucket,
            "key": output_key,
        },
        "stats": {
            "pageCount": len(pages),
            "chunkCount": len(chunks),
            "createdAt": now,
        },
        "chunks": [
            {
                "chunkId": chunk.chunk_id,
                "index": chunk.index,
                "text": chunk.text,
                "pageStart": chunk.page_start,
                "pageEnd": chunk.page_end,
                "tokenCountEstimate": chunk.token_count_estimate,
                "metadata": {
                    "fileId": file_id,
                    "clientId": document.metadata.get("client-id"),
                    "userId": document.metadata.get("user-id"),
                    "fileType": document.metadata.get("file-type"),
                    "fileSubType": document.metadata.get("file-sub-type"),
                    "docType": document.metadata.get("doc-type"),
                    "stage": document.metadata.get("stage"),
                    "parentFolder": document.metadata.get("parent-folder"),
                    "uploadedBy": document.metadata.get("uploaded-by"),
                    "tags": _parse_tags(document.metadata.get("tags")),
                },
            }
            for chunk in chunks
        ],
    }


def build_completion_payload(output_bucket: str, output_key: str, chunk_payload: dict) -> dict:
    return {
        "eventType": "DOCUMENT_CHUNKING_COMPLETED",
        "schemaVersion": chunk_payload["schemaVersion"],
        "fileId": chunk_payload["fileId"],
        "chunkArtifact": {
            "bucket": output_bucket,
            "key": output_key,
        },
        "source": {
            "bucket": chunk_payload["source"]["bucket"],
            "key": chunk_payload["source"]["key"],
        },
        "stats": chunk_payload["stats"],
    }


def _parse_tags(raw: str | None) -> list[dict[str, str]]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _safe_stem(key: str) -> str:
    return key.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def _request_shutdown(signum: int, _frame: object) -> None:
    global shutdown_requested
    logger.info("Shutdown requested", extra={"signal": signum})
    shutdown_requested = True


if __name__ == "__main__":
    sys.exit(main())
