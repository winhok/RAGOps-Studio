from __future__ import annotations

import os
import uuid
from abc import ABC, abstractmethod

from app.core.embeddings import EmbeddingProvider
from app.core.models import Chunk
from app.core.text import cosine_similarity


class DenseIndex(ABC):
    @abstractmethod
    def rank(self, query: str, chunks: list[Chunk]) -> list[tuple[str, float]]:
        raise NotImplementedError


class InMemoryDenseIndex(DenseIndex):
    def __init__(self, embedding_provider: EmbeddingProvider) -> None:
        self.embedding_provider = embedding_provider

    def rank(self, query: str, chunks: list[Chunk]) -> list[tuple[str, float]]:
        q = self.embedding_provider.embed(query)
        ranked = [
            (chunk.id, cosine_similarity(q, self.embedding_provider.embed(chunk.text)))
            for chunk in chunks
        ]
        return sorted(ranked, key=lambda item: item[1], reverse=True)


class QdrantDenseIndex(DenseIndex):
    """Qdrant-backed dense retrieval.

    The document/version/ACL source of truth remains SQLite. Qdrant stores vectors
    plus chunk identifiers; stale vectors are ignored because results are intersected
    with the active, ACL-approved chunk set before fusion.
    """

    def __init__(self, embedding_provider: EmbeddingProvider, *, url: str | None = None, collection: str = "ragops_chunks") -> None:
        from qdrant_client import QdrantClient

        self.embedding_provider = embedding_provider
        self.url = url or os.getenv("QDRANT_URL", "http://localhost:6333")
        self.collection = collection
        self.client = QdrantClient(url=self.url)

    @staticmethod
    def _point_id(chunk_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ragops:{chunk_id}"))

    def _ensure_collection(self, dimensions: int) -> None:
        from qdrant_client.models import Distance, VectorParams

        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=dimensions, distance=Distance.COSINE),
            )

    def rank(self, query: str, chunks: list[Chunk]) -> list[tuple[str, float]]:
        if not chunks:
            return []
        from qdrant_client.models import PointStruct

        vectors = [(chunk, self.embedding_provider.embed(chunk.text)) for chunk in chunks]
        self._ensure_collection(len(vectors[0][1]))
        self.client.upsert(
            collection_name=self.collection,
            wait=True,
            points=[
                PointStruct(
                    id=self._point_id(chunk.id),
                    vector=vector,
                    payload={"chunk_id": chunk.id, "source_id": chunk.source_id, "version": chunk.version},
                )
                for chunk, vector in vectors
            ],
        )
        allowed = {chunk.id for chunk in chunks}
        response = self.client.query_points(
            collection_name=self.collection,
            query=self.embedding_provider.embed(query),
            limit=min(max(len(chunks) * 2, 10), 100),
            with_payload=True,
        )
        ranked: list[tuple[str, float]] = []
        for point in response.points:
            chunk_id = (point.payload or {}).get("chunk_id")
            if isinstance(chunk_id, str) and chunk_id in allowed:
                ranked.append((chunk_id, float(point.score)))
        return ranked
