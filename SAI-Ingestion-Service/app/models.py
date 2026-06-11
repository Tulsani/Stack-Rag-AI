from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DocumentTag(BaseModel):
    key: str
    value: str


class UploadMetadata(BaseModel):
    client_id: str = Field(alias="clientId")
    user_id: str = Field(alias="userId")
    file_type: str = Field(alias="fileType")
    file_sub_type: str | None = Field(default=None, alias="fileSubType")
    doc_type: str | None = Field(default=None, alias="docType")
    stage: str | None = None
    parent_folder: str | None = Field(default=None, alias="parentFolder")
    uploaded_by: str | None = Field(default=None, alias="uploadedBy")
    description: str | None = None
    linked: bool = False
    tags: list[DocumentTag] = Field(default_factory=list)


class ParsedUploadRequest(BaseModel):
    filename: str
    content_type: str
    file_size_bytes: int
    metadata: UploadMetadata


class UploadInitResponse(BaseModel):
    fileId: str
    uploadUrl: str
    s3Key: str
    expiresIn: int
    metadata: dict[str, Any]
