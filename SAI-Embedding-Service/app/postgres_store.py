from __future__ import annotations

import json
from collections.abc import Sequence

import psycopg

from .models import ChunkRecord


class PostgresChunkStore:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def replace_file_chunks(
        self,
        file_id: str,
        chunks: Sequence[ChunkRecord],
        embeddings: Sequence[list[float]],
    ) -> int:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")

        with psycopg.connect(self.dsn) as conn:
            with conn.transaction():
                conn.execute("DELETE FROM chunks WHERE file_id = %s", (file_id,))
                with conn.cursor() as cur:
                    cur.executemany(
                        """
                        INSERT INTO chunks (
                            file_id,
                            filename,
                            client_id,
                            user_id,
                            file_type,
                            file_sub_type,
                            doc_type,
                            stage,
                            page_start,
                            page_end,
                            chunk_index,
                            content,
                            embedding,
                            metadata
                        )
                        VALUES (
                            %(file_id)s,
                            %(filename)s,
                            %(client_id)s,
                            %(user_id)s,
                            %(file_type)s,
                            %(file_sub_type)s,
                            %(doc_type)s,
                            %(stage)s,
                            %(page_start)s,
                            %(page_end)s,
                            %(chunk_index)s,
                            %(content)s,
                            %(embedding)s::vector,
                            %(metadata)s::jsonb
                        )
                        """,
                        [
                            {
                                "file_id": chunk.file_id,
                                "filename": chunk.filename,
                                "client_id": chunk.client_id,
                                "user_id": chunk.user_id,
                                "file_type": chunk.file_type,
                                "file_sub_type": chunk.file_sub_type,
                                "doc_type": chunk.doc_type,
                                "stage": chunk.stage,
                                "page_start": chunk.page_start,
                                "page_end": chunk.page_end,
                                "chunk_index": chunk.chunk_index,
                                "content": chunk.content,
                                "embedding": _to_pgvector(embedding),
                                "metadata": json.dumps(chunk.metadata, ensure_ascii=False),
                            }
                            for chunk, embedding in zip(chunks, embeddings, strict=True)
                        ],
                    )
        return len(chunks)


def _to_pgvector(embedding: Sequence[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in embedding) + "]"
