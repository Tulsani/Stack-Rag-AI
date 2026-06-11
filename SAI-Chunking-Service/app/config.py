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
    output_bucket: str
    completion_topic_arn: str
    mistral_api_key: str
    mistral_ocr_model: str
    chunk_target_tokens: int
    chunk_overlap_tokens: int
    sqs_wait_time_seconds: int
    sqs_visibility_timeout_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        required = {
            "CHUNKING_QUEUE_URL": os.getenv("CHUNKING_QUEUE_URL"),
            "CHUNK_OUTPUT_BUCKET": os.getenv("CHUNK_OUTPUT_BUCKET"),
            "CHUNK_COMPLETE_TOPIC_ARN": os.getenv("CHUNK_COMPLETE_TOPIC_ARN"),
            "MISTRAL_API_KEY": os.getenv("MISTRAL_API_KEY"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

        return cls(
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            queue_url=required["CHUNKING_QUEUE_URL"],
            output_bucket=required["CHUNK_OUTPUT_BUCKET"],
            completion_topic_arn=required["CHUNK_COMPLETE_TOPIC_ARN"],
            mistral_api_key=required["MISTRAL_API_KEY"],
            mistral_ocr_model=os.getenv("MISTRAL_OCR_MODEL", "mistral-ocr-latest"),
            chunk_target_tokens=_int_env("CHUNK_TARGET_TOKENS", 700),
            chunk_overlap_tokens=_int_env("CHUNK_OVERLAP_TOKENS", 100),
            sqs_wait_time_seconds=_int_env("SQS_WAIT_TIME_SECONDS", 20),
            sqs_visibility_timeout_seconds=_int_env("SQS_VISIBILITY_TIMEOUT_SECONDS", 900),
        )
