from __future__ import annotations

import logging
import os
import signal
import sys
import time

from app.aws_io import AwsIO, chunk_artifacts_from_sqs_body
from app.chunk_payload import parse_chunk_payload
from app.config import Settings
from app.mistral_embeddings import MistralEmbeddingClient
from app.models import ChunkRecord
from app.postgres_store import PostgresChunkStore

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)
shutdown_requested = False


def main() -> int:
    settings = Settings.from_env()
    aws = AwsIO(region_name=settings.aws_region)
    embeddings = MistralEmbeddingClient(
        api_key=settings.mistral_api_key,
        model=settings.mistral_embed_model,
        expected_dimension=settings.embedding_dimension,
    )
    store = PostgresChunkStore(settings.postgres_dsn)

    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    logger.info("Embedding worker started")
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
                process_message(settings, aws, embeddings, store, message["Body"])
            except Exception:
                logger.exception("Message processing failed; leaving message for retry")
            else:
                aws.delete_message(settings.queue_url, receipt_handle)

    logger.info("Embedding worker stopped")
    return 0


def process_message(
    settings: Settings,
    aws: AwsIO,
    embeddings: MistralEmbeddingClient,
    store: PostgresChunkStore,
    body: str,
) -> None:
    artifacts = chunk_artifacts_from_sqs_body(body)
    if not artifacts:
        return

    for artifact in artifacts:
        started = time.monotonic()
        payload = aws.fetch_json(artifact.bucket, artifact.key)
        chunks = parse_chunk_payload(payload)
        if not chunks:
            logger.warning(
                "Chunk artifact contained no embeddable chunks",
                extra={"bucket": artifact.bucket, "key": artifact.key},
            )
            continue

        vectors = embed_chunks(embeddings, chunks, settings.embedding_batch_size)
        inserted = store.replace_file_chunks(file_id=chunks[0].file_id, chunks=chunks, embeddings=vectors)

        logger.info(
            "Embedded chunk artifact",
            extra={
                "file_id": chunks[0].file_id,
                "chunk_artifact_bucket": artifact.bucket,
                "chunk_artifact_key": artifact.key,
                "inserted_chunks": inserted,
                "duration_seconds": round(time.monotonic() - started, 3),
            },
        )


def embed_chunks(
    embeddings: MistralEmbeddingClient,
    chunks: list[ChunkRecord],
    batch_size: int,
) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        vectors.extend(embeddings.embed_texts([chunk.content for chunk in batch]))
    return vectors


def _request_shutdown(signum: int, _frame: object) -> None:
    global shutdown_requested
    logger.info("Shutdown requested", extra={"signal": signum})
    shutdown_requested = True


if __name__ == "__main__":
    sys.exit(main())
