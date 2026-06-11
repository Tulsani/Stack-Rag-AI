from __future__ import annotations

import base64
import logging
import mimetypes

import httpx

from .models import ExtractedPage, StoredDocument

logger = logging.getLogger(__name__)

IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/webp",
}

DOCUMENT_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class MistralOcrClient:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def extract_pages(self, document: StoredDocument) -> list[ExtractedPage]:
        content_type = _normalise_content_type(document)
        data_url = f"data:{content_type};base64,{base64.b64encode(document.body).decode('ascii')}"

        payload = {
            "model": self.model,
            "document": _build_document_payload(content_type, data_url),
            "include_image_base64": False,
        }

        with httpx.Client(timeout=httpx.Timeout(120.0)) as client:
            response = client.post(
                "https://api.mistral.ai/v1/ocr",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=payload,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "Mistral OCR request failed",
                    extra={
                        "status_code": response.status_code,
                        "content_type": content_type,
                        "document_type": payload["document"]["type"],
                        "source_bucket": document.bucket,
                        "source_key": document.key,
                        "response_body": response.text[:1000],
                    },
                )
                raise RuntimeError(
                    f"Mistral OCR failed with HTTP {response.status_code}: {response.text[:500]}"
                ) from exc
            result = response.json()

        pages = []
        for i, page in enumerate(result.get("pages", []), start=1):
            confidence = None
            scores = page.get("confidence_scores") or {}
            if "average_page_confidence_score" in scores:
                confidence = float(scores["average_page_confidence_score"])

            pages.append(
                ExtractedPage(
                    page_number=int(page.get("index", i - 1)) + 1,
                    text=(page.get("markdown") or "").strip(),
                    confidence=confidence,
                )
            )
        return [page for page in pages if page.text]


def extract_plain_text(document: StoredDocument) -> list[ExtractedPage]:
    text = document.body.decode("utf-8", errors="replace").strip()
    return [ExtractedPage(page_number=1, text=text)] if text else []


def should_use_ocr(document: StoredDocument) -> bool:
    content_type = _normalise_content_type(document)
    return content_type in DOCUMENT_CONTENT_TYPES | IMAGE_CONTENT_TYPES


def _normalise_content_type(document: StoredDocument) -> str:
    content_type = (document.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type != "application/octet-stream":
        return content_type
    guessed, _ = mimetypes.guess_type(document.key)
    return guessed or "application/octet-stream"


def _build_document_payload(content_type: str, data_url: str) -> dict[str, str]:
    if content_type in IMAGE_CONTENT_TYPES:
        return {
            "type": "image_url",
            "image_url": data_url,
        }
    if content_type in DOCUMENT_CONTENT_TYPES:
        return {
            "type": "document_url",
            "document_url": data_url,
        }
    raise ValueError(f"Unsupported OCR content type: {content_type}")
