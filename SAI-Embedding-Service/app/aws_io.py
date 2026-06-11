from __future__ import annotations

import json
import logging

import boto3

from .models import ChunkArtifactRef, JsonDict

logger = logging.getLogger(__name__)


class AwsIO:
    def __init__(self, region_name: str) -> None:
        self.s3 = boto3.client("s3", region_name=region_name)
        self.sqs = boto3.client("sqs", region_name=region_name)

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

    def fetch_json(self, bucket: str, key: str) -> JsonDict:
        response = self.s3.get_object(Bucket=bucket, Key=key)
        return json.loads(response["Body"].read().decode("utf-8"))


def chunk_artifacts_from_sqs_body(body: str) -> list[ChunkArtifactRef]:
    event = json.loads(body)

    if "Message" in event:
        event = json.loads(event["Message"])

    if event.get("eventType") == "DOCUMENT_CHUNKING_COMPLETED":
        artifact = event["chunkArtifact"]
        return [
            ChunkArtifactRef(
                bucket=artifact["bucket"],
                key=artifact["key"],
                file_id=event.get("fileId"),
            )
        ]

    artifacts = []
    for record in event.get("Records", []):
        body = record.get("body")
        if not body:
            continue
        artifacts.extend(chunk_artifacts_from_sqs_body(body))

    if not artifacts:
        logger.warning("SQS message did not contain chunk artifact references")
    return artifacts
