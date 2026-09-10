from __future__ import annotations

from dataclasses import replace

from app.core.bm25 import BM25Index
from app.core.embeddings import EmbeddingProvider, HashEmbeddingProvider
from app.core.models import Chunk, RetrievalHit
from app.core.rrf import reciprocal_rank_fusion
from app.core.text import overlap_score
from app.services.vector_index import DenseIndex, InMemoryDenseIndex


class HybridRetriever:
    def __init__(self, embedding_provider: EmbeddingProvider | None = None, dense_index: DenseIndex | None = None) -> None:
        self.embedding_provider = embedding_provider or HashEmbeddingProvider()
        self.dense_index = dense_index or InMemoryDenseIndex(self.embedding_provider)

    def retrieve(self, query: str, chunks: list[Chunk], *, top_k: int = 5) -> list[RetrievalHit]:
        if not chunks:
            return []

        bm25 = BM25Index([chunk.text for chunk in chunks])
        lexical_rank = bm25.rank(query)
        lexical_scores = {chunks[idx].id: score for idx, score in lexical_rank}

        dense_rank = self.dense_index.rank(query, chunks)
        dense_scores = dict(dense_rank)

        lexical_ids = [chunks[idx].id for idx, _ in lexical_rank]
        dense_ids = [chunk_id for chunk_id, _ in dense_rank]
        fused = reciprocal_rank_fusion([lexical_ids, dense_ids])

        hits = [
            RetrievalHit(
                chunk=chunk,
                score=fused.get(chunk.id, 0.0),
                dense_score=dense_scores.get(chunk.id, 0.0),
                lexical_score=lexical_scores.get(chunk.id, 0.0),
                rrf_score=fused.get(chunk.id, 0.0),
            )
            for chunk in chunks
        ]
        hits.sort(key=lambda hit: hit.rrf_score, reverse=True)

        # Lightweight reranking layer. In production this can be swapped for a
        # cross-encoder or provider rerank API without changing the pipeline.
        reranked: list[RetrievalHit] = []
        candidate_count = min(len(hits), max(top_k * 3, 8))
        for hit in hits[:candidate_count]:
            semantic = max(hit.dense_score, 0.0)
            overlap = overlap_score(query, hit.chunk.text)
            rerank = 0.55 * overlap + 0.30 * semantic + 0.15 * min(hit.lexical_score / 5.0, 1.0)
            reranked.append(replace(hit, rerank_score=rerank, score=rerank))

        reranked.sort(key=lambda hit: (hit.rerank_score, hit.rrf_score), reverse=True)
        return reranked[:top_k]
