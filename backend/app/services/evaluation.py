from __future__ import annotations

from dataclasses import asdict

from app.core.metrics import EvaluationSummary, keyword_coverage, ndcg_at_k, recall_at_k, reciprocal_rank
from app.core.models import BenchmarkCase
from app.services.pipeline import RAGPipeline


class Evaluator:
    def __init__(self, pipeline: RAGPipeline) -> None:
        self.pipeline = pipeline

    def evaluate(self, cases: list[BenchmarkCase], *, k: int = 5) -> dict:
        rows = []
        recalls = []
        reciprocal_ranks = []
        ndcgs = []
        coverages = []

        for case in cases:
            answer = self.pipeline.run(case.query, role=case.role, top_k=k)
            trace = self.pipeline.store.get_trace(answer.trace_id) or {}
            retrieved_sources = list(dict.fromkeys(row["source_id"] for row in trace.get("retrieval", [])))
            relevant = set(case.relevant_source_ids)
            recall = recall_at_k(retrieved_sources, relevant, k)
            rr = reciprocal_rank(retrieved_sources, relevant)
            ndcg = ndcg_at_k(retrieved_sources, relevant, k)
            coverage = keyword_coverage(answer.text, case.expected_keywords)

            recalls.append(recall)
            reciprocal_ranks.append(rr)
            ndcgs.append(ndcg)
            coverages.append(coverage)
            rows.append(
                {
                    "query": case.query,
                    "role": case.role,
                    "relevant_source_ids": list(case.relevant_source_ids),
                    "retrieved_source_ids": retrieved_sources,
                    "recall_at_k": round(recall, 4),
                    "reciprocal_rank": round(rr, 4),
                    "ndcg_at_k": round(ndcg, 4),
                    "keyword_coverage": round(coverage, 4),
                    "answer": answer.text,
                    "trace_id": answer.trace_id,
                }
            )

        count = max(len(cases), 1)
        summary = EvaluationSummary(
            cases=len(cases),
            recall_at_k=round(sum(recalls) / count, 4),
            mrr=round(sum(reciprocal_ranks) / count, 4),
            ndcg_at_k=round(sum(ndcgs) / count, 4),
            keyword_coverage=round(sum(coverages) / count, 4),
        )
        return {"summary": summary.as_dict(), "cases": rows}
