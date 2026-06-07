from __future__ import annotations

import json
import logging
from typing import Iterable
from urllib.parse import unquote_plus

import boto3

from .models import JsonDict, S3Document, StoredDocument

logger = logging.getLogger(__name__)


class AwsIO:
    def __init__(self, region_name: str) -> None:
        self.s3 = boto3.client("s3", region_name=region_name)
        self.sqs = boto3.client("sqs", region_name=region_name)
        self.sns = boto3.client("sns", region_name=region_name)

    def receive_messages(
        self,
        queue_url: str,
        wait_time_seconds: int,
        visibility_timeout_seconds: int,
        max_messages: int = 1,
    ) -> list[JsonDict]:
        response = self.sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=wait_time_seconds,
            VisibilityTimeout=visibility_timeout_seconds,
            MessageAttributeNames=["All"],
        )
        return response.get("Messages", [])

    def delete_message(self, queue_url: str, receipt_handle: str) -> None:
        self.sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)

    def fetch_document(self, doc: S3Document) -> StoredDocument:
        response = self.s3.get_object(Bucket=doc.bucket, Key=doc.key)
        return StoredDocument(
            bucket=doc.bucket,
            key=doc.key,
            body=response["Body"].read(),
            content_type=response.get("ContentType") or "application/octet-stream",
            metadata=response.get("Metadata") or {},
        )

    def write_json(self, bucket: str, key: str, payload: JsonDict) -> None:
        self.s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )

    def publish_completion(self, topic_arn: str, payload: JsonDict) -> None:
        self.sns.publish(
            TopicArn=topic_arn,
            Subject="RAG chunking complete",
            Message=json.dumps(payload, ensure_ascii=False),
        )


def s3_documents_from_sqs_body(body: str) -> list[S3Document]:
    event = json.loads(body)

    if "Message" in event:
        event = json.loads(event["Message"])

    records: Iterable[JsonDict] = event.get("Records", [])
    docs: list[S3Document] = []
    for record in records:
        if not record.get("eventSource", "").endswith(":s3"):
            logger.info("Skipping non-S3 event record", extra={"record": record})
            continue

        s3 = record["s3"]
        docs.append(
            S3Document(
                bucket=s3["bucket"]["name"],
                key=unquote_plus(s3["object"]["key"]),
                etag=s3["object"].get("eTag"),
                sequencer=s3["object"].get("sequencer"),
            )
        )
    return docs
