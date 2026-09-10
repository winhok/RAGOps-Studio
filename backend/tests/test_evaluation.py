from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.models import BenchmarkCase
from app.services.evaluation import Evaluator
from app.services.pipeline import RAGPipeline
from app.services.store import SQLiteDocumentStore


class EvaluationTests(unittest.TestCase):
    def test_evaluator_reports_retrieval_metrics(self) -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        store = SQLiteDocumentStore(tmp.name)
        store.ingest(
            source_id="shipping",
            title="Shipping",
            content="Standard shipping arrives in 3 to 5 business days. Tracking issues after 72 hours require investigation.",
        )
        result = Evaluator(RAGPipeline(store)).evaluate(
            [BenchmarkCase(query="When do tracking issues require investigation?", relevant_source_ids=("shipping",))]
        )
        self.assertEqual(result["summary"]["cases"], 1)
        self.assertEqual(result["summary"]["recall_at_k"], 1.0)
        self.assertEqual(result["summary"]["mrr"], 1.0)


if __name__ == "__main__":
    unittest.main()
