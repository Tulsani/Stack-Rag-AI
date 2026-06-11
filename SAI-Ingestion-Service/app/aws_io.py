from __future__ import annotations

import json
from typing import Any

import boto3
from botocore.exceptions import ClientError

from .config import MIME_TO_EXTENSION
from .models import UploadMetadata


class FileRecordConflictError(RuntimeError):
    pass


class AwsIngestionStore:
    def __init__(self, upload_bucket: str, documents_table: str, presign_expiry_seconds: int) -> None:
        self.upload_bucket = upload_bucket
        self.documents_table = documents_table
        self.presign_expiry_seconds = presign_expiry_seconds
        self.s3 = boto3.client("s3")
        self.dynamodb = boto3.resource("dynamodb")

    def build_s3_key(self, file_id: str, metadata: UploadMetadata, extension: str) -> str:
        parts = [metadata.client_id]
        if metadata.parent_folder:
            parts.append(metadata.parent_folder.strip("/"))
        parts.append(f"{file_id}.{extension}")
        return "/".join(part for part in parts if part)

    def generate_presigned_put_url(
        self,
        file_id: str,
        content_type: str,
        metadata: UploadMetadata,
    ) -> dict[str, Any]:
        extension = MIME_TO_EXTENSION[content_type]
        s3_key = self.build_s3_key(file_id, metadata, extension)

        upload_url = self.s3.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": self.upload_bucket,
                "Key": s3_key,
                "ContentType": content_type,
                "Metadata": self._build_s3_object_metadata(file_id, metadata),
            },
            ExpiresIn=self.presign_expiry_seconds,
        )

        return {
            "uploadUrl": upload_url,
            "s3Key": s3_key,
            "expiresIn": self.presign_expiry_seconds,
        }

    def persist_file_record(self, record: dict[str, Any]) -> None:
        try:
            self.dynamodb.Table(self.documents_table).put_item(
                Item=record,
                ConditionExpression="attribute_not_exists(fileId)",
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code == "ConditionalCheckFailedException":
                raise FileRecordConflictError(record["fileId"]) from exc
            raise

    def _build_s3_object_metadata(self, file_id: str, metadata: UploadMetadata) -> dict[str, str]:
        return {
            "file-id": file_id,
            "client-id": metadata.client_id,
            "user-id": metadata.user_id,
            "file-type": metadata.file_type,
            "file-sub-type": metadata.file_sub_type or "",
            "doc-type": metadata.doc_type or "",
            "stage": metadata.stage or "",
            "parent-folder": metadata.parent_folder or "",
            "uploaded-by": metadata.uploaded_by or "",
            "linked": str(metadata.linked).lower(),
            "tags": json.dumps([tag.model_dump() for tag in metadata.tags]),
            "description": metadata.description or "",
        }
