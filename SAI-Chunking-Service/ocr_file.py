from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import httpx


MISTRAL_OCR_URL = "https://api.mistral.ai/v1/ocr"
TOKEN_PATTERN = re.compile(r"\S+")
PARAGRAPH_SPLIT_PATTERN = re.compile(r"\n\s*\n+")


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


def build_pages(ocr_result: dict) -> list[dict]:
    pages = []

    for i, page in enumerate(ocr_result.get("pages", []), start=1):
        scores = page.get("confidence_scores") or {}
        confidence = scores.get("average_page_confidence_score")

        text = (page.get("markdown") or "").strip()
        if not text:
            continue

        pages.append(
            {
                "pageNumber": int(page.get("index", i - 1)) + 1,
                "text": text,
                "confidence": confidence,
            }
        )

    return pages


def chunk_pages(
    pages: list[dict],
    target_tokens: int = 700,
    overlap_tokens: int = 100,
) -> list[dict]:
    if target_tokens <= 0:
        raise ValueError("target_tokens must be greater than zero")

    if overlap_tokens < 0 or overlap_tokens >= target_tokens:
        raise ValueError("overlap_tokens must be non-negative and smaller than target_tokens")

    paragraphs: list[tuple[int, str]] = []

    for page in pages:
        page_number = page["pageNumber"]

        for paragraph in PARAGRAPH_SPLIT_PATTERN.split(page["text"]):
            cleaned = " ".join(paragraph.split())
            if cleaned:
                paragraphs.append((page_number, cleaned))

    chunks = []
    current_parts: list[str] = []
    current_pages: list[int] = []
    current_tokens = 0

    for page_number, paragraph in paragraphs:
        paragraph_tokens = count_tokens(paragraph)

        if current_parts and current_tokens + paragraph_tokens > target_tokens:
            chunks.append(
                build_chunk(
                    index=len(chunks),
                    parts=current_parts,
                    pages=current_pages,
                    token_count=current_tokens,
                )
            )

            current_parts, current_pages, current_tokens = overlap_seed(
                chunks[-1]["text"],
                overlap_tokens,
            )

        if paragraph_tokens > target_tokens:
            slices = slice_words(paragraph, target_tokens)

            for slice_text in slices:
                if current_parts:
                    chunks.append(
                        build_chunk(
                            index=len(chunks),
                            parts=current_parts,
                            pages=current_pages,
                            token_count=current_tokens,
                        )
                    )

                    current_parts, current_pages, current_tokens = overlap_seed(
                        chunks[-1]["text"],
                        overlap_tokens,
                    )

                current_parts.append(slice_text)
                current_pages.append(page_number)
                current_tokens = count_tokens(slice_text)

        else:
            current_parts.append(paragraph)
            current_pages.append(page_number)
            current_tokens += paragraph_tokens

    if current_parts:
        chunks.append(
            build_chunk(
                index=len(chunks),
                parts=current_parts,
                pages=current_pages,
                token_count=current_tokens,
            )
        )

    return chunks


def build_chunk(
    index: int,
    parts: list[str],
    pages: list[int],
    token_count: int,
) -> dict:
    text = "\n\n".join(parts).strip()
    digest = sha256(text.encode("utf-8")).hexdigest()[:16]

    return {
        "chunkId": f"chunk_{index:05d}_{digest}",
        "index": index,
        "text": text,
        "pageStart": min(pages) if pages else None,
        "pageEnd": max(pages) if pages else None,
        "tokenCountEstimate": token_count,
    }


def overlap_seed(text: str, overlap_tokens: int) -> tuple[list[str], list[int], int]:
    if overlap_tokens == 0:
        return [], [], 0

    words = TOKEN_PATTERN.findall(text)
    overlap = " ".join(words[-overlap_tokens:])

    return ([overlap] if overlap else []), [], count_tokens(overlap)


def slice_words(text: str, max_tokens: int) -> list[str]:
    words = TOKEN_PATTERN.findall(text)
    return [
        " ".join(words[i : i + max_tokens])
        for i in range(0, len(words), max_tokens)
    ]


def count_tokens(text: str) -> int:
    return len(TOKEN_PATTERN.findall(text))


def build_output_payload(
    file_path: Path,
    pages: list[dict],
    chunks: list[dict],
) -> dict:
    return {
        "schemaVersion": "local-ocr-chunk-v1",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "fileName": file_path.name,
            "absolutePath": str(file_path.resolve()),
            "contentType": guess_content_type(file_path),
            "sizeBytes": file_path.stat().st_size,
        },
        "stats": {
            "pageCount": len(pages),
            "chunkCount": len(chunks),
        },
        "pages": pages,
        "chunks": chunks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Mistral OCR and simple chunking.")
    parser.add_argument("file", help="Path to local PDF/image/document")
    parser.add_argument("--target-tokens", type=int, default=700)
    parser.add_argument("--overlap-tokens", type=int, default=100)
    parser.add_argument(
        "--model",
        default=os.getenv("MISTRAL_OCR_MODEL", "mistral-ocr-latest"),
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("MISTRAL_API_KEY"),
        help="Defaults to MISTRAL_API_KEY env var.",
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

    pages = build_pages(ocr_result)

    if not pages:
        raise RuntimeError("No text extracted from document.")

    chunks = chunk_pages(
        pages=pages,
        target_tokens=args.target_tokens,
        overlap_tokens=args.overlap_tokens,
    )

    output_payload = build_output_payload(
        file_path=file_path,
        pages=pages,
        chunks=chunks,
    )

    output_path = file_path.with_name(f"{file_path.stem}.ocr.chunks.json")
    output_path.write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Pages extracted: {len(pages)}")
    print(f"Chunks created: {len(chunks)}")
    print(f"Wrote JSON to: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())