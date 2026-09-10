from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.rrf import reciprocal_rank_fusion
from app.services.pipeline import RAGPipeline
from app.services.store import SQLiteDocumentStore


class CoreTests(unittest.TestCase):
    def make_store(self) -> SQLiteDocumentStore:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return SQLiteDocumentStore(tmp.name)

    def test_rrf_rewards_consensus(self) -> None:
        scores = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a", "d"]])
        self.assertGreater(scores["a"], scores["c"])
        self.assertGreater(scores["b"], scores["d"])

    def test_document_versioning_and_dedup(self) -> None:
        store = self.make_store()
        first, duplicate = store.ingest(source_id="policy", title="Policy", content="Version one policy text long enough.")
        self.assertFalse(duplicate)
        same, duplicate = store.ingest(source_id="policy", title="Policy", content="Version one policy text long enough.")
        self.assertTrue(duplicate)
        self.assertEqual(first.id, same.id)

        second, duplicate = store.ingest(source_id="policy", title="Policy", content="Version two policy text changed significantly.")
        self.assertFalse(duplicate)
        self.assertEqual(second.version, 2)
        docs = store.list_documents(include_inactive=True)
        active = [doc for doc in docs if doc.active]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].version, 2)

    def test_acl_prevents_public_access_to_internal_doc(self) -> None:
        store = self.make_store()
        store.ingest(
            source_id="public-policy",
            title="Public",
            content="Public shipping information is available to all users and customers.",
            allowed_roles=("public",),
        )
        store.ingest(
            source_id="internal-policy",
            title="Internal",
            content="Secret escalation code zebra-nine is available only to support agents.",
            allowed_roles=("support",),
        )
        pipeline = RAGPipeline(store)
        public_answer = pipeline.run("What is the secret escalation code?", role="public")
        public_trace = store.get_trace(public_answer.trace_id)
        self.assertNotIn("internal-policy", [row["source_id"] for row in public_trace["retrieval"]])

        support_answer = pipeline.run("What is the secret escalation code?", role="support")
        support_trace = store.get_trace(support_answer.trace_id)
        self.assertIn("internal-policy", [row["source_id"] for row in support_trace["retrieval"]])

    def test_trace_contains_component_scores(self) -> None:
        store = self.make_store()
        store.ingest(
            source_id="refund",
            title="Refund",
            content="Refunds for unused products are allowed within 30 days after delivery.",
        )
        answer = RAGPipeline(store).run("How many days do I have to request a refund?")
        trace = store.get_trace(answer.trace_id)
        self.assertTrue(trace["retrieval"])
        first = trace["retrieval"][0]
        self.assertIn("dense_score", first)
        self.assertIn("lexical_score", first)
        self.assertIn("rrf_score", first)
        self.assertIn("rerank_score", first)


if __name__ == "__main__":
    unittest.main()
