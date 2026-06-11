from __future__ import annotations

import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(frozen=True)
class Settings:
    aws_region: str
    queue_url: str
    mistral_api_key: str
    mistral_embed_model: str
    embedding_batch_size: int
    embedding_dimension: int
    sqs_wait_time_seconds: int
    sqs_visibility_timeout_seconds: int
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_sslmode: str

    @classmethod
    def from_env(cls) -> "Settings":
        required = {
            "EMBEDDING_QUEUE_URL": os.getenv("EMBEDDING_QUEUE_URL"),
            "MISTRAL_API_KEY": os.getenv("MISTRAL_API_KEY"),
            "POSTGRES_HOST": os.getenv("POSTGRES_HOST"),
            "POSTGRES_DB": os.getenv("POSTGRES_DB"),
            "POSTGRES_USER": os.getenv("POSTGRES_USER"),
            "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

        return cls(
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            queue_url=required["EMBEDDING_QUEUE_URL"],
            mistral_api_key=required["MISTRAL_API_KEY"],
            mistral_embed_model=os.getenv("MISTRAL_EMBED_MODEL", "mistral-embed"),
            embedding_batch_size=_int_env("EMBEDDING_BATCH_SIZE", 32),
            embedding_dimension=_int_env("EMBEDDING_DIMENSION", 1024),
            sqs_wait_time_seconds=_int_env("SQS_WAIT_TIME_SECONDS", 20),
            sqs_visibility_timeout_seconds=_int_env("SQS_VISIBILITY_TIMEOUT_SECONDS", 900),
            postgres_host=required["POSTGRES_HOST"],
            postgres_port=_int_env("POSTGRES_PORT", 5432),
            postgres_db=required["POSTGRES_DB"],
            postgres_user=required["POSTGRES_USER"],
            postgres_password=required["POSTGRES_PASSWORD"],
            postgres_sslmode=os.getenv("POSTGRES_SSLMODE", "require"),
        )

    @property
    def postgres_dsn(self) -> str:
        return (
            f"host={self.postgres_host} "
            f"port={self.postgres_port} "
            f"dbname={self.postgres_db} "
            f"user={self.postgres_user} "
            f"password={self.postgres_password} "
            f"sslmode={self.postgres_sslmode}"
        )
