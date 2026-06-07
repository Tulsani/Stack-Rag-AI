from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx


MISTRAL_OCR_URL = "https://api.mistral.ai/v1/ocr"


def guess_content_type(file_path: Path) -> str:
    content_type, _ = mimetypes.guess_type(file_path.name)
    return content_type or "application/octet-stream"


def run_mistral_ocr(file_path: Path, api_key: str, model: str) -> dict:
    file_bytes = file_path.read_bytes()
    content_type = guess_content_type(file_path)

    data_url = (
        f"data:{content_type};base64,"
        f"{base64.b64encode(file_bytes).decode('ascii')}"
    )

    payload = {
        "model": model,
        "document": {
            "type": "document_url",
            "document_url": data_url,
        },
        "include_image_base64": False,
    }

    with httpx.Client(timeout=httpx.Timeout(180.0)) as client:
        response = client.post(
            MISTRAL_OCR_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
        )

    response.raise_for_status()
    return response.json()


def build_output_payload(file_path: Path, ocr_result: dict) -> dict:
    pages = []

    for i, page in enumerate(ocr_result.get("pages", []), start=1):
        scores = page.get("confidence_scores") or {}
        confidence = scores.get("average_page_confidence_score")

        pages.append(
            {
                "pageNumber": int(page.get("index", i - 1)) + 1,
                "text": (page.get("markdown") or "").strip(),
                "confidence": confidence,
            }
        )

    return {
        "schemaVersion": "local-ocr-v1",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "fileName": file_path.name,
            "absolutePath": str(file_path.resolve()),
            "contentType": guess_content_type(file_path),
            "sizeBytes": file_path.stat().st_size,
        },
        "stats": {
            "pageCount": len(pages),
            "nonEmptyPageCount": sum(1 for page in pages if page["text"]),
        },
        "pages": pages,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Mistral OCR on a local file.")
    parser.add_argument("file", help="Path to local PDF/image/document")
    parser.add_argument(
        "--model",
        default=os.getenv("MISTRAL_OCR_MODEL", "mistral-ocr-latest"),
        help="Mistral OCR model name",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("MISTRAL_API_KEY"),
        help="Mistral API key. Defaults to MISTRAL_API_KEY env var.",
    )

    args = parser.parse_args()

    if not args.api_key:
        raise RuntimeError("Missing API key. Set MISTRAL_API_KEY or pass --api-key.")

    file_path = Path(args.file).expanduser().resolve()

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    print(f"Running OCR for: {file_path.name}")

    ocr_result = run_mistral_ocr(
        file_path=file_path,
        api_key=args.api_key,
        model=args.model,
    )

    output_payload = build_output_payload(file_path, ocr_result)

    output_path = file_path.with_name(f"{file_path.stem}.ocr.json")
    output_path.write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote OCR JSON to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())