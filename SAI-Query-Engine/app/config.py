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


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


@dataclass(frozen=True)
class Settings:
    mistral_api_key: str
    mistral_embed_model: str
    mistral_chat_model: str
    mistral_query_rewrite_model: str
    embedding_dimension: int
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_sslmode: str
    default_top_k: int
    min_similarity: float

    @classmethod
    def from_env(cls) -> "Settings":
        required = {
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
            mistral_api_key=required["MISTRAL_API_KEY"],
            mistral_embed_model=os.getenv("MISTRAL_EMBED_MODEL", "mistral-embed"),
            mistral_chat_model=os.getenv("MISTRAL_CHAT_MODEL", "mistral-small-latest"),
            mistral_query_rewrite_model=os.getenv("MISTRAL_QUERY_REWRITE_MODEL", "mistral-small-latest"),
            embedding_dimension=_int_env("EMBEDDING_DIMENSION", 1024),
            postgres_host=required["POSTGRES_HOST"],
            postgres_port=_int_env("POSTGRES_PORT", 5432),
            postgres_db=required["POSTGRES_DB"],
            postgres_user=required["POSTGRES_USER"],
            postgres_password=required["POSTGRES_PASSWORD"],
            postgres_sslmode=os.getenv("POSTGRES_SSLMODE", "require"),
            default_top_k=_int_env("DEFAULT_TOP_K", 5),
            min_similarity=_float_env("MIN_SIMILARITY", 0.2),
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
