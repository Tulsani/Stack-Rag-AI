from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_PRESIGN_EXPIRY_SECONDS = 900
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024

MIME_TO_EXTENSION = {
    "application/pdf": "pdf",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/tiff": "tiff",
    "image/webp": "webp",
    "text/plain": "txt",
    "text/csv": "csv",
}

SUPPORTED_MIME_TYPES = set(MIME_TO_EXTENSION)


@dataclass(frozen=True)
class Settings:
    api_key: str
    upload_bucket: str
    documents_table: str
    presign_expiry_seconds: int
    cors_origins: list[str]

    @classmethod
    def from_env(cls) -> "Settings":
        api_key = os.getenv("API_KEY","f3fedd47-3784-4508-b1a6-d0be676a8dc7")
        upload_bucket = os.getenv("UPLOAD_BUCKET")
        documents_table = os.getenv("DOCUMENTS_TABLE")

        missing = [
            name
            for name, value in (
                ("UPLOAD_BUCKET", upload_bucket),
                ("DOCUMENTS_TABLE", documents_table),
                ("API_KEY", api_key),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

        cors_origins = os.getenv("CORS_ORIGINS") or os.getenv("CORS_ORIGIN") or "*"

        return cls(
            api_key=api_key,
            upload_bucket=upload_bucket,
            documents_table=documents_table,
            presign_expiry_seconds=int(
                os.getenv("PRESIGN_EXPIRY_SECONDS", str(DEFAULT_PRESIGN_EXPIRY_SECONDS))
            ),
            cors_origins=[origin.strip() for origin in cors_origins.split(",") if origin.strip()],
        )
