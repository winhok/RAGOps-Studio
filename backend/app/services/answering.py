from __future__ import annotations

from app.core.models import Citation, RetrievalHit
from app.core.text import overlap_score, split_sentences


class ExtractiveAnswerer:
    """Offline answerer for demos/tests.

    It deliberately avoids fabricating content: answers are composed from the
    highest-scoring source sentences and always include citations.
    """

    def answer(self, query: str, hits: list[RetrievalHit], *, max_sentences: int = 4) -> tuple[str, list[Citation], float]:
        if not hits:
            return (
                "I don't have enough information in the approved knowledge base to answer that.",
                [],
                0.0,
            )

        candidates: list[tuple[float, RetrievalHit, str]] = []
        for hit in hits:
            for sentence in split_sentences(hit.chunk.text):
                score = 0.65 * overlap_score(query, sentence) + 0.35 * max(hit.score, 0.0)
                candidates.append((score, hit, sentence))
        candidates.sort(key=lambda item: item[0], reverse=True)

        selected: list[tuple[RetrievalHit, str]] = []
        seen = set()
        for score, hit, sentence in candidates:
            normalized = sentence.lower().strip()
            if normalized in seen:
                continue
            if score <= 0 and selected:
                continue
            seen.add(normalized)
            selected.append((hit, sentence))
            if len(selected) >= max_sentences:
                break

        if not selected:
            return (
                "I don't have enough information in the approved knowledge base to answer that.",
                [],
                0.0,
            )

        text = " ".join(sentence for _, sentence in selected)
        citations: list[Citation] = []
        used_chunks = set()
        for hit, sentence in selected:
            if hit.chunk.id in used_chunks:
                continue
            used_chunks.add(hit.chunk.id)
            citations.append(
                Citation(
                    source_id=hit.chunk.source_id,
                    title=hit.chunk.title,
                    chunk_id=hit.chunk.id,
                    quote=sentence[:220],
                    score=round(hit.score, 4),
                )
            )
        confidence = min(1.0, 0.35 + sum(max(hit.score, 0.0) for hit in hits[:3]) * 2.4)
        return text, citations, round(confidence, 3)
