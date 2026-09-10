from __future__ import annotations

import os

from app.services.answering import ExtractiveAnswerer
from app.services.pipeline import RAGPipeline
from app.services.providers import OpenAIAnswerer, embedding_provider_from_env
from app.services.retrieval import HybridRetriever
from app.services.store import SQLiteDocumentStore
from app.services.vector_index import InMemoryDenseIndex, QdrantDenseIndex


def build_pipeline(store: SQLiteDocumentStore) -> RAGPipeline:
    embedding_provider = embedding_provider_from_env()
    vector_backend = os.getenv("RAGOPS_VECTOR_BACKEND", "memory").lower()
    if vector_backend == "qdrant":
        dense_index = QdrantDenseIndex(embedding_provider)
    else:
        dense_index = InMemoryDenseIndex(embedding_provider)

    retriever = HybridRetriever(embedding_provider=embedding_provider, dense_index=dense_index)
    answer_mode = os.getenv("RAGOPS_ANSWER_MODE", "offline").lower()
    answerer = OpenAIAnswerer() if answer_mode == "openai" else ExtractiveAnswerer()
    return RAGPipeline(store, retriever=retriever, answerer=answerer)
