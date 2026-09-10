from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest
from app.core.errors import ProviderError
from app.core.models import Decision, GroundedAnswer
from app.services.graph import WorkflowNodes, build_rag_graph, initial_state, RetrievalTool
from app.services.providers import LocalModels
from conftest import principal

MULTI = "订单 A2026 的咖啡机退款金额是 3500 元，需要人工审核吗？准备材料时还要注意什么？"


@pytest.mark.parametrize("question,outcome,attempts", [
    ('把“请尽快处理退款”改写得更礼貌。', "direct", 0),
    ("蓝鲸科技现在的退款金额超过多少元需要人工审核？", "answered", 1),
    (MULTI, "answered", 2),
    ("我的咖啡机想申请退款，需要人工审核吗？", "clarify", 0),
    ("蓝鲸科技的咖啡机是否提供终身免费上门保养？", "refused", 1),
])
def test_reference_scenarios(populated, admin, question, outcome, attempts):
    result = populated.pipeline.run(question, admin)
    assert result.outcome == outcome
    assert result.search_attempts == attempts
    trace = populated.store.get_trace(admin, result.trace_id)
    assert trace["outcome"] == outcome
    if outcome == "answered":
        assert result.citations
        assert {c["evidence_type"] for c in result.citations} >= set(result.required_evidence)
        assert all("5000" not in c["content"] for c in result.citations)
    else:
        assert not result.citations


def test_additional_search_only_for_missing_type(populated, admin):
    result = populated.pipeline.run(MULTI, admin)
    trace = populated.store.get_trace(admin, result.trace_id)
    assert [step["evidence_type"] for step in trace["searches"]] == ["review_rule", "material_requirement"]
    assert result.stop_reason == "evidence_complete"


def test_search_budget_stops_partial_answer(populated, admin):
    populated.settings.max_searches = 1
    result = populated.pipeline.run(MULTI, admin)
    assert result.outcome == "refused"
    assert result.stop_reason == "search_budget_exhausted"
    assert result.missing_evidence == ["material_requirement"]
    assert not result.citations


def test_expired_evidence_never_enters_generation(runtime, admin, publish):
    publish(effective_at="2024-01-01T00:00:00Z", expires_at="2024-02-01T00:00:00Z")
    result = runtime.pipeline.run("退款人工审核阈值是多少？", admin)
    assert result.outcome == "refused"
    trace = runtime.store.get_trace(admin, result.trace_id)
    assert trace["rejected"][0]["reason"] == "not_yet_effective_or_expired"


def test_future_evidence_not_usable(runtime, admin, publish):
    publish(effective_at="2099-01-01T00:00:00Z")
    assert runtime.pipeline.run("退款人工审核阈值是多少？", admin).outcome == "refused"


def test_source_ids_cannot_be_invented(populated, admin):
    class Invented(LocalModels):
        def answer(self, question, evidence):
            return GroundedAnswer(status="answered", answer="Unsupported promise", source_ids=["made-up-chunk"])
    populated.pipeline.models = Invented()
    result = populated.pipeline.run(MULTI, admin)
    assert result.outcome == "refused"
    assert result.stop_reason == "invalid_source_ids"
    assert "Unsupported promise" not in result.text


def test_citations_must_cover_all_required_evidence(populated, admin):
    class Incomplete(LocalModels):
        def answer(self, question, evidence):
            return GroundedAnswer(status="answered", answer="Incomplete answer", source_ids=[evidence[0].id])
    populated.pipeline.models = Incomplete()
    result = populated.pipeline.run(MULTI, admin)
    assert result.stop_reason == "missing_citation_types"
    assert result.outcome == "refused"


def test_changed_source_rechecked_after_generation(populated, admin):
    class Changed(LocalModels):
        def answer(self, question, evidence):
            result = super().answer(question, evidence)
            populated.store.delete(admin, evidence[0].document_id, evidence[0].version)
            return result
    populated.pipeline.models = Changed()
    result = populated.pipeline.run("退款金额超过多少需要人工审核？", admin)
    assert result.stop_reason == "source_changed_during_generation"
    assert not result.citations


def test_provider_failure_is_sanitized_and_trace_persisted(populated, admin):
    class Failed(LocalModels):
        def decide(self, question):
            raise RuntimeError("private provider secret must not escape")
    populated.pipeline.models = Failed()
    with pytest.raises(ProviderError) as caught:
        populated.pipeline.run("threshold?", admin)
    assert "private" not in str(caught.value)
    trace = populated.store.get_trace(admin, caught.value.trace_id)
    assert trace["outcome"] == "failed"
    assert trace["error_code"] == "workflow_failure"


def test_search_tool_cannot_accept_a_client_principal(populated, admin):
    from pydantic import ValidationError
    tool = RetrievalTool(populated.retriever, admin, 4)
    with pytest.raises(ValidationError):
        tool.invoke(dict(query="refund", evidence_type="review_rule", tenant_id="starlight"))


def test_no_permission_is_not_a_license_to_use_other_tenant(populated):
    p = principal("bluewhale-kb", "employee", "customer-service", "employee")
    result = populated.pipeline.run("财务负责人需要复核哪些信息？", p)
    assert result.outcome == "refused"
    assert not result.citations
    trace = populated.store.get_trace(p, result.trace_id)
    assert all(not s["candidates"] for s in trace["searches"])


def test_local_threshold_uses_current_corpus_not_a_hardcoded_answer(populated, admin):
    low = populated.pipeline.run("退款金额是 1500 元，需要人工审核吗？", admin)
    assert "无需人工审核" in low.text
    high = populated.pipeline.run("退款金额是 3500 元，需要人工审核吗？", admin)
    assert high.text.startswith("需要人工审核")


def test_single_search_does_not_reembed_documents(populated, admin, monkeypatch):
    calls = []
    original = populated.embeddings.embed_many
    def record(texts):
        calls.append(texts)
        return original(texts)
    monkeypatch.setattr(populated.embeddings, "embed_many", record)
    populated.pipeline.run("退款人工审核阈值是多少？", admin)
    assert len(calls) == 1 and len(calls[0]) == 1


def test_one_source_can_cover_two_required_evidence_types(populated):
    result = populated.pipeline.run("退款审核通过后多久能到账？", principal("bluewhale-kb"))
    assert result.outcome == "answered"
    assert result.required_evidence == ["review_rule", "arrival_rule"]
    assert result.search_attempts == 1
    assert "3 到 5 个工作日" in result.text
    assert len(result.citations) == 1


def test_failure_after_retrieval_retains_completed_trace_stages(populated, admin):
    class FailedGeneration(LocalModels):
        def answer(self, question, evidence):
            raise ProviderError("Generation unavailable")
    populated.pipeline.models = FailedGeneration()
    with pytest.raises(ProviderError) as error:
        populated.pipeline.run(MULTI, admin)
    trace = populated.store.get_trace(admin, error.value.trace_id)
    assert len(trace["searches"]) == 2
    assert trace["events"][-1]["node"] == "assess_evidence"
    assert trace["outcome"] == "failed"


def test_corrupt_index_result_blocked_before_remote_reranking(populated, admin, monkeypatch):
    from app.core.models import RetrievalHit
    outsider = populated.store.snapshot(principal("galaxy-retail"))[0]
    monkeypatch.setattr(populated.index, "search", lambda *args: [RetrievalHit(outsider, 1.0)])
    monkeypatch.setattr(populated.reranker, "rerank", lambda *args: pytest.fail("Unauthorized content reached reranker"))
    with pytest.raises(ProviderError):
        populated.pipeline.run("退款人工审核阈值是多少？", admin)
