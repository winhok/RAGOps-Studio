from __future__ import annotations

import os

from app.core.embeddings import EmbeddingProvider, HashEmbeddingProvider
from app.core.models import Citation, RetrievalHit


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        from openai import OpenAI

        self.model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL") or None,
        )

    def embed(self, text: str) -> list[float]:
        response = self.client.embeddings.create(model=self.model, input=text)
        return list(response.data[0].embedding)


class OpenAIAnswerer:
    def __init__(self) -> None:
        from openai import OpenAI

        self.model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL") or None,
        )

    def answer(self, query: str, hits: list[RetrievalHit], *, max_sentences: int = 4) -> tuple[str, list[Citation], float]:
        if not hits:
            return "I don't have enough information in the approved knowledge base to answer that.", [], 0.0

        context = "\n\n".join(
            f"[SOURCE {idx}] {hit.chunk.title} | {hit.chunk.source_id}\n{hit.chunk.text}"
            for idx, hit in enumerate(hits, start=1)
        )
        system = (
            "You are a grounded support assistant. Answer only from the supplied sources. "
            "If the sources do not support the answer, say you do not have enough information. "
            "Do not invent policy details. Keep the answer concise."
        )
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Question: {query}\n\nSources:\n{context}"},
            ],
        )
        text = response.choices[0].message.content or ""
        citations = [
            Citation(
                source_id=hit.chunk.source_id,
                title=hit.chunk.title,
                chunk_id=hit.chunk.id,
                quote=hit.chunk.text[:220],
                score=round(hit.score, 4),
            )
            for hit in hits[:3]
        ]
        confidence = min(0.95, 0.45 + sum(max(hit.score, 0.0) for hit in hits[:3]) * 2.0)
        return text.strip(), citations, round(confidence, 3)


def embedding_provider_from_env() -> EmbeddingProvider:
    mode = os.getenv("RAGOPS_EMBEDDING_MODE", "offline").lower()
    if mode == "openai":
        return OpenAIEmbeddingProvider()
    return HashEmbeddingProvider()
