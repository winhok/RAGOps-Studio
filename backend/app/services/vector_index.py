from __future__ import annotations
import json
import uuid
from typing import Protocol
from app.core.bm25 import BM25Index
from app.core.config import Settings
from app.core.models import Chunk, Principal, RetrievalHit
from app.core.errors import ConfigurationError, ProviderError
from app.core.rrf import reciprocal_rank_fusion
from app.core.text import cosine_similarity

class HybridIndex(Protocol):

    def stage(self, chunks: list[Chunk]) -> None:
        ...

    def search(self, query: str, vector: list[float], chunks: list[Chunk], principal: Principal, limit: int) -> list[RetrievalHit]:
        ...

    def close(self) -> None:
        ...

def permission_filter(principal: Principal, allowed_ids: list[str] | None=None) -> str:
    # Values are JSON-quoted; neither user text nor model output can supply filter syntax.
    quote = lambda value: json.dumps(value, ensure_ascii=False)
    parts = [f'tenant_id == {quote(principal.tenant_id)}']
    if principal.role != 'admin':
        parts.append(f'(visibility == "company" or department_id == {quote(principal.department_id)})')
    if allowed_ids is not None:
        parts.append('chunk_id in ' + json.dumps(allowed_ids))
    return ' and '.join(parts)

def fuse(chunks: list[Chunk], lexical: list[tuple[str, float]], dense: list[tuple[str, float]], limit: int) -> list[RetrievalHit]:
    scores = reciprocal_rank_fusion([[cid for cid, value in lexical if value > 0], [cid for cid, _ in dense]])
    ls, ds = (dict(lexical), dict(dense))
    hits = [RetrievalHit(chunk=c, score=scores.get(c.id, 0), dense_score=ds.get(c.id), lexical_score=ls.get(c.id), rrf_score=scores.get(c.id, 0)) for c in chunks if c.id in scores]
    return sorted(hits, key=lambda hit: (hit.score, hit.chunk.id), reverse=True)[:limit]

class LocalHybridIndex:

    def stage(self, chunks: list[Chunk]) -> None:
        if any((not c.vector for c in chunks)):
            raise ProviderError('Cannot index an empty vector')

    def search(self, query: str, vector: list[float], chunks: list[Chunk], principal: Principal, limit: int) -> list[RetrievalHit]:
        if not chunks:
            return []
        dense = sorted([(c.id, cosine_similarity(vector, c.vector)) for c in chunks], key=lambda item: item[1], reverse=True)
        lexical = [(chunks[i].id, score) for i, score in BM25Index([c.text for c in chunks]).rank(query)]
        return fuse(chunks, lexical, dense, limit)

    def close(self):
        pass

class MilvusHybridIndex:

    def __init__(self, settings: Settings, *, client=None):
        try:
            from pymilvus import MilvusClient
        except ImportError as exc:
            raise ConfigurationError('Install backend/requirements-integrations.txt to use Milvus') from exc
        self.settings = settings
        self.client = client or MilvusClient(uri=settings.milvus_uri, token=settings.milvus_token, timeout=settings.timeout_seconds)
        self.collection = settings.collection
        self._ensure_collection()

    def _ensure_collection(self):
        from pymilvus import DataType, Function, FunctionType
        if not self.client.has_collection(self.collection):
            schema = self.client.create_schema(auto_id=False, enable_dynamic_field=False)
            schema.add_field('chunk_id', DataType.VARCHAR, is_primary=True, max_length=128)
            schema.add_field('tenant_id', DataType.VARCHAR, max_length=96, is_partition_key=True)
            for name in ('department_id', 'visibility', 'evidence_type'):
                schema.add_field(name, DataType.VARCHAR, max_length=96)
            schema.add_field('content', DataType.VARCHAR, max_length=8192, enable_analyzer=True, analyzer_params={'tokenizer': 'jieba', 'filter': ['removepunct']})
            schema.add_field('dense_vector', DataType.FLOAT_VECTOR, dim=self.settings.dimensions)
            schema.add_field('sparse_vector', DataType.SPARSE_FLOAT_VECTOR)
            schema.add_function(Function(name='content_bm25', input_field_names=['content'], output_field_names=['sparse_vector'], function_type=FunctionType.BM25))
            indexes = self.client.prepare_index_params()
            indexes.add_index(field_name='dense_vector', index_type='AUTOINDEX', metric_type='COSINE')
            indexes.add_index(field_name='sparse_vector', index_type='SPARSE_INVERTED_INDEX', metric_type='BM25', params={'inverted_index_algo': 'DAAT_MAXSCORE'})
            self.client.create_collection(collection_name=self.collection, schema=schema, index_params=indexes, num_partitions=16, consistency_level='Strong')
        else:
            description = self.client.describe_collection(self.collection)
            fields = {field['name']: field for field in description['fields']}
            if not {'chunk_id', 'tenant_id', 'department_id', 'visibility', 'evidence_type', 'content', 'dense_vector', 'sparse_vector'} <= fields.keys():
                raise ConfigurationError('Milvus collection schema does not match RAGOps v2; choose a new collection')
            if int(fields['dense_vector'].get('params', {}).get('dim', 0)) != self.settings.dimensions:
                raise ConfigurationError('Milvus vector dimension mismatch')
        self.client.load_collection(self.collection)

    def stage(self, chunks: list[Chunk]):
        rows = [{'chunk_id': c.id, 'tenant_id': c.tenant_id, 'department_id': c.department_id, 'visibility': c.visibility, 'evidence_type': c.evidence_type, 'content': c.text, 'dense_vector': c.vector} for c in chunks]
        self.client.upsert(collection_name=self.collection, data=rows)
        self.client.flush(self.collection)

    def search(self, query: str, vector: list[float], chunks: list[Chunk], principal: Principal, limit: int) -> list[RetrievalHit]:
        if not chunks:
            return []
        from pymilvus import AnnSearchRequest, RRFRanker
        expr = permission_filter(principal, [c.id for c in chunks])
        requests = [AnnSearchRequest(data=[vector], anns_field='dense_vector', param={'metric_type': 'COSINE', 'params': {}}, expr=expr, limit=limit), AnnSearchRequest(data=[query], anns_field='sparse_vector', param={'metric_type': 'BM25', 'params': {}}, expr=expr, limit=limit)]
        result = self.client.hybrid_search(collection_name=self.collection, reqs=requests, ranker=RRFRanker(k=60), limit=limit, output_fields=['chunk_id'], consistency_level='Strong')
        by_id = {c.id: c for c in chunks}
        hits = []
        for row in result[0]:
            cid = str(row['id'])
            if cid not in by_id:
                raise ProviderError('Vector backend returned a chunk outside the authorized snapshot')
            score = float(row['distance'])
            hits.append(RetrievalHit(chunk=by_id[cid], score=score, rrf_score=score))
        return hits

    def close(self):
        self.client.close()

class QdrantHybridIndex:
    """Preserved backend: filtered dense search in Qdrant, authorized BM25 and RRF in-process."""

    def __init__(self, settings: Settings):
        try:
            from qdrant_client import QdrantClient, models
        except ImportError as exc:
            raise ConfigurationError('Install backend/requirements-integrations.txt to use Qdrant') from exc
        self.client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None, timeout=settings.timeout_seconds)
        self.collection, self.dimensions = (settings.collection, settings.dimensions)
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(self.collection, vectors_config=models.VectorParams(size=self.dimensions, distance=models.Distance.COSINE))
        else:
            current = self.client.get_collection(self.collection).config.params.vectors
            if getattr(current, 'size', None) != self.dimensions:
                raise ConfigurationError('Qdrant vector dimension mismatch')

    def stage(self, chunks: list[Chunk]):
        from qdrant_client import models
        self.client.upsert(collection_name=self.collection, wait=True, points=[models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, c.id)), vector=c.vector, payload={'chunk_id': c.id, 'tenant_id': c.tenant_id, 'department_id': c.department_id, 'visibility': c.visibility}) for c in chunks])

    def search(self, query: str, vector: list[float], chunks: list[Chunk], principal: Principal, limit: int) -> list[RetrievalHit]:
        if not chunks:
            return []
        from qdrant_client import models
        conditions = [models.FieldCondition(key='tenant_id', match=models.MatchValue(value=principal.tenant_id)), models.FieldCondition(key='chunk_id', match=models.MatchAny(any=[c.id for c in chunks]))]
        # The immutable-ID allow list already encodes department ACL and active version state.
        result = self.client.query_points(self.collection, query=vector, query_filter=models.Filter(must=conditions), limit=limit, with_payload=True)
        dense = [(p.payload['chunk_id'], p.score) for p in result.points]
        if not {cid for cid, _ in dense} <= {c.id for c in chunks}:
            raise ProviderError('Unauthorized index result')
        lexical = [(chunks[i].id, score) for i, score in BM25Index([c.text for c in chunks]).rank(query)]
        return fuse(chunks, lexical, dense, limit)

    def close(self):
        self.client.close()
