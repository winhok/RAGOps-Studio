from __future__ import annotations

import hashlib

from .models import Chunk, Document


def chunk_document(document: Document, *, chunk_size: int = 650, overlap: int = 100) -> list[Chunk]:
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be larger than overlap")

    text = document.content.strip()
    if not text:
        return []

    chunks: list[Chunk] = []
    cursor = 0
    index = 0
    while cursor < len(text):
        end = min(len(text), cursor + chunk_size)
        if end < len(text):
            boundary = max(text.rfind("\n", cursor, end), text.rfind(". ", cursor, end), text.rfind("。", cursor, end))
            if boundary > cursor + chunk_size // 2:
                end = boundary + 1
        piece = text[cursor:end].strip()
        if piece:
            digest = hashlib.sha1(f"{document.id}:{index}:{piece}".encode("utf-8")).hexdigest()[:12]
            chunks.append(
                Chunk(
                    id=f"chk_{digest}",
                    document_id=document.id,
                    source_id=document.source_id,
                    title=document.title,
                    text=piece,
                    version=document.version,
                    allowed_roles=document.allowed_roles,
                    metadata={**document.metadata, "chunk_index": index},
                )
            )
            index += 1
        if end >= len(text):
            break
        cursor = max(cursor + 1, end - overlap)
    return chunks
