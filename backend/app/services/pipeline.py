from __future__ import annotations

import time
import uuid
from dataclasses import asdict

from app.core.models import Answer
from app.services.answering import ExtractiveAnswerer
from app.services.retrieval import HybridRetriever
from app.services.store import SQLiteDocumentStore


class RAGPipeline:
    def __init__(self, store: SQLiteDocumentStore, *, retriever: HybridRetriever | None = None, answerer=None) -> None:
        self.store = store
        self.retriever = retriever or HybridRetriever()
        self.answerer = answerer or ExtractiveAnswerer()

    def run(self, query: str, *, role: str = "public", top_k: int = 5) -> Answer:
        trace_id = f"tr_{uuid.uuid4().hex[:14]}"
        timings: dict[str, float] = {}
        started = time.perf_counter()

        t0 = time.perf_counter()
        chunks = self.store.active_chunks(role=role)
        timings["acl_filter"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        hits = self.retriever.retrieve(query, chunks, top_k=top_k)
        timings["hybrid_retrieval_and_rerank"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        text, citations, confidence = self.answerer.answer(query, hits)
        timings["answer_generation"] = (time.perf_counter() - t0) * 1000
        timings["total"] = (time.perf_counter() - started) * 1000

        route = "answer" if citations and confidence >= 0.4 else "refuse"
        answer = Answer(
            text=text,
            citations=citations,
            trace_id=trace_id,
            confidence=confidence,
            timings_ms={key: round(value, 2) for key, value in timings.items()},
            route=route,
        )
        self.store.save_trace(
            trace_id,
            {
                "trace_id": trace_id,
                "query": query,
                "role": role,
                "route": route,
                "confidence": confidence,
                "timings_ms": answer.timings_ms,
                "retrieval": [
                    {
                        "chunk_id": hit.chunk.id,
                        "source_id": hit.chunk.source_id,
                        "title": hit.chunk.title,
                        "dense_score": round(hit.dense_score, 4),
                        "lexical_score": round(hit.lexical_score, 4),
                        "rrf_score": round(hit.rrf_score, 5),
                        "rerank_score": round(hit.rerank_score, 4),
                    }
                    for hit in hits
                ],
                "citations": [asdict(citation) for citation in citations],
            },
        )
        return answer
