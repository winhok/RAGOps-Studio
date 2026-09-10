import json
import math

import httpx
import pytest
from app.core.errors import ProviderError
from app.core.models import RetrievalHit
from app.services.providers import HttpTransport, Embeddings, ChatModels, Reranker


def transport(handler, attempts=3):
    return HttpTransport(attempts=attempts, client=httpx.Client(transport=httpx.MockTransport(handler), timeout=1), sleep=lambda _: None)


def test_rate_limit_retry_is_bounded_and_authorized():
    requests = []
    def handler(request):
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer fixture-key"
        return httpx.Response(429 if len(requests) < 3 else 200, json={"ok": True})
    with_provider = transport(handler)
    try:
        assert with_provider.post("https://provider.invalid/chat", "fixture-key", {}) == {"ok": True}
        assert len(requests) == 3
    finally:
        with_provider.close()


@pytest.mark.parametrize("status,expected_calls", [(401, 1), (403, 1), (429, 3), (500, 3)])
def test_failure_never_exposes_provider_body(status, expected_calls):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"secret": "do-not-release"})
    t = transport(handler)
    try:
        with pytest.raises(ProviderError) as e:
            t.post("https://provider.invalid/chat", "fixture-key", {})
        assert len(calls) == expected_calls
        assert "do-not-release" not in str(e.value)
        assert "fixture-key" not in str(e.value)
    finally:
        t.close()


def test_timeout_is_bounded():
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("internal detail", request=request)
    t = transport(handler, attempts=2)
    try:
        with pytest.raises(ProviderError):
            t.post("https://provider.invalid/chat", "fixture-key", {})
        assert len(calls) == 2
    finally:
        t.close()


def test_embedding_response_order_is_restored(settings):
    settings = settings.model_copy(update={"embedding_provider": "zhipu", "zhipu_api_key": "fixture", "embedding_model": "fixture", "dimensions": 256})
    t = transport(lambda _: httpx.Response(200, json={"data": [{"index": 1, "embedding": [2.0] * 256}, {"index": 0, "embedding": [1.0] * 256}]}))
    try:
        vectors = Embeddings(settings, t).embed_many(["A", "B"])
        assert [v[0] for v in vectors] == [1.0, 2.0]
    finally:
        t.close()


@pytest.mark.parametrize("response", [
    {"data": []},
    {"data": [{"index": 3, "embedding": [0] * 256}]},
    {"data": [{"index": 0, "embedding": [0]}]},
    {"data": [{"index": 0, "embedding": ["bad"] * 256}]},
])
def test_malformed_embeddings_fail_closed(settings, response):
    settings = settings.model_copy(update={"embedding_provider": "zhipu", "zhipu_api_key": "fixture", "embedding_model": "fixture", "dimensions": 256})
    t = transport(lambda _: httpx.Response(200, json=response))
    try:
        with pytest.raises(ProviderError):
            Embeddings(settings, t).embed_many(["A"])
    finally:
        t.close()


def test_malformed_chat_json_is_a_provider_error(settings):
    settings = settings.model_copy(update={"model_provider": "zhipu", "zhipu_api_key": "fixture", "chat_model": "fixture"})
    t = transport(lambda _: httpx.Response(200, json={"choices": [{"message": {"content": "not JSON"}}]}))
    try:
        with pytest.raises(ProviderError):
            ChatModels(settings, t).decide("refund?")
    finally:
        t.close()


def test_model_cannot_request_unknown_evidence_types(settings):
    settings = settings.model_copy(update={"model_provider": "deepseek", "deepseek_api_key": "fixture", "chat_model": "fixture"})
    result = {"route": "retrieve", "required_evidence": ["exfiltrate_all_tenants"], "reason": "Ignore policy"}
    t = transport(lambda _: httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(result)}}]}))
    try:
        with pytest.raises(ProviderError):
            ChatModels(settings, t).decide("refund?")
    finally:
        t.close()


def test_reranker_rejects_invalid_indexes(settings, runtime, admin, publish):
    publish()
    hit = RetrievalHit(runtime.store.snapshot(admin)[0], 0.1)
    settings = settings.model_copy(update={"rerank_provider": "zhipu", "zhipu_api_key": "fixture"})
    t = transport(lambda _: httpx.Response(200, json={"results": [{"index": 50, "relevance_score": 0.9}]}))
    try:
        with pytest.raises(ProviderError):
            Reranker(settings, t).rerank("refund", [hit], 1)
    finally:
        t.close()


def test_rerank_request_uses_only_authorized_candidates(settings, populated):
    from conftest import principal
    p = principal("bluewhale-kb", "employee", "customer-service")
    settings = settings.model_copy(update={"rerank_provider": "zhipu", "zhipu_api_key": "fixture"})
    bodies = []
    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        return httpx.Response(200, json={"results": [{"index": 0, "relevance_score": 0.9}]})
    t = transport(handler)
    populated.retriever.reranker = Reranker(settings, t)
    try:
        populated.pipeline.run("客服初审需要多久？", p)
        assert bodies
        assert "财务对账" not in str(bodies)
        assert "STAR-88" not in str(bodies)
    finally:
        t.close()
