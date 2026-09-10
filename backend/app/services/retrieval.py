from __future__ import annotations
import time
from dataclasses import asdict
from app.core.models import Principal
from app.core.errors import ProviderError
from dataclasses import replace
from app.services.vector_index import permission_filter

class HybridRetriever:

    def __init__(self, store, embeddings, index, reranker):
        self.store, self.embeddings, self.index, self.reranker = (store, embeddings, index, reranker)

    def retrieve(self, query: str, principal: Principal, evidence_type: str, top_k: int=4):
        started = time.perf_counter()
        chunks = self.store.snapshot(principal, evidence_type)
        acl_ms = (time.perf_counter() - started) * 1000
        if not chunks:
            return ([], {'acl': round(acl_ms, 2), 'embedding': 0, 'retrieval': 0, 'rerank': 0}, 0)
        now = time.perf_counter()
        vector = self.embeddings.embed(query)
        embed_ms = (time.perf_counter() - now) * 1000
        now = time.perf_counter()
        hits = self.index.search(query, vector, chunks, principal, max(12, top_k * 3))
        retrieval_ms = (time.perf_counter() - now) * 1000
        authorized = {chunk.id: chunk for chunk in chunks}
        if any((hit.chunk.id not in authorized for hit in hits)):
            raise ProviderError('Index result was outside the authorized snapshot')
        hits = [replace(hit, chunk=authorized[hit.chunk.id]) for hit in hits]
        now = time.perf_counter()
        hits = self.reranker.rerank(query, hits, top_k)
        rerank_ms = (time.perf_counter() - now) * 1000
        return (hits, {'acl': round(acl_ms, 2), 'embedding': round(embed_ms, 2), 'retrieval': round(retrieval_ms, 2), 'rerank': round(rerank_ms, 2)}, len(chunks))

def hit_record(hit) -> dict:
    c = hit.chunk
    return {'chunk_id': c.id, 'document_id': c.document_id, 'title': c.title, 'version': c.version, 'evidence_type': c.evidence_type, 'content': c.text, 'dense_score': hit.dense_score, 'lexical_score': hit.lexical_score, 'rrf_score': hit.rrf_score, 'rerank_score': hit.rerank_score, 'source_path': c.source_path, 'effective_at': c.effective_at, 'expires_at': c.expires_at}
