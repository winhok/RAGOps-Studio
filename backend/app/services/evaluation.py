from __future__ import annotations
from app.core.metrics import keyword_coverage, ndcg_at_k, recall_at_k, reciprocal_rank
from app.core.models import BenchmarkCase, Principal

class Evaluator:

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def evaluate(self, cases: list[BenchmarkCase], principal: Principal, k: int=5) -> dict:
        if not cases:
            raise ValueError('Evaluation dataset must not be empty')
        rows = []
        for case in cases:
            answer = self.pipeline.run(case.query, principal, top_k=k)
            trace = self.pipeline.store.get_trace(principal, answer.trace_id)
            retrieved = list(dict.fromkeys((r['document_id'] for search in trace['searches'] for r in search['candidates'])))
            relevant = set(case.relevant_source_ids)
            rows.append({'query': case.query, 'relevant_source_ids': list(relevant), 'retrieved_source_ids': retrieved, 'recall_at_k': round(recall_at_k(retrieved, relevant, k), 4), 'reciprocal_rank': round(reciprocal_rank(retrieved, relevant), 4), 'ndcg_at_k': round(ndcg_at_k(retrieved, relevant, k), 4), 'keyword_coverage': round(keyword_coverage(answer.text, case.expected_keywords), 4), 'outcome': answer.outcome, 'trace_id': answer.trace_id})
        avg = lambda name: round(sum((row[name] for row in rows)) / len(rows), 4)
        return {'summary': {'cases': len(rows), 'recall_at_k': avg('recall_at_k'), 'mrr': avg('reciprocal_rank'), 'ndcg_at_k': avg('ndcg_at_k'), 'keyword_coverage': avg('keyword_coverage')}, 'cases': rows, 'runtime': self.pipeline.settings.public_runtime(), 'dataset': 'synthetic-policy-regression-v2', 'metric_scope': 'Document-level ranking across retrieval rounds; synthetic regression data, not production accuracy.', 'k': k}
