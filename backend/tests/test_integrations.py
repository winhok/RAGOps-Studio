"""Opt-in checks never substitute a fake server for a claimed live integration."""
import os
import uuid
import pytest

from app.services.graph import WorkflowNodes, build_rag_graph, initial_state


def test_langgraph_runs_the_same_real_retrieval_nodes(populated, admin):
    pytest.importorskip("langgraph.graph", reason="Optional LangGraph SDK is not installed")
    pytest.importorskip("langchain_core.tools", reason="Optional LangChain SDK is not installed")
    nodes = WorkflowNodes(populated.models, populated.retriever, admin, populated.store, use_langchain=True)
    state = build_rag_graph(nodes, "langgraph").invoke(initial_state("退款金额 3500 元，需要人工审核吗？还需要什么材料？"))
    assert state["outcome"] == "answered"
    assert state["search_attempts"] == 2


@pytest.mark.integration
def test_live_milvus_native_hybrid_acl(settings, admin):
    if os.getenv("RUN_MILVUS_TESTS") != "1":
        pytest.skip("Set RUN_MILVUS_TESTS=1 with a running Milvus 2.6 instance")
    pytest.importorskip("pymilvus")
    from app.services.runtime import Runtime
    from bootstrap import seed
    from conftest import principal
    settings = settings.model_copy(update={"vector_backend": "milvus", "milvus_uri": os.getenv("MILVUS_URI", settings.milvus_uri), "collection": "ragops_test_" + uuid.uuid4().hex[:12]})
    rt = Runtime(settings)
    try:
        seed(rt)
        assert rt.pipeline.run("退款金额 3500 元，需要人工审核吗？还需要什么材料？", admin).outcome == "answered"
        support = principal("bluewhale-kb", "employee", "customer-service")
        assert rt.pipeline.run("财务负责人需要复核哪些信息？", support).outcome == "refused"
    finally:
        rt.index.client.drop_collection(rt.index.collection)
        rt.close()


@pytest.mark.integration
def test_live_zhipu_embeddings_rerank_and_chat(settings):
    if os.getenv("RUN_ZHIPU_TESTS") != "1":
        pytest.skip("Set RUN_ZHIPU_TESTS=1 and configure valid Zhipu model access; API calls incur cost")
    from app.core.config import Settings
    from app.services.runtime import Runtime
    from bootstrap import seed
    from conftest import principal
    configured = Settings(root=settings.root, state_dir=settings.state_dir, principals_file=settings.principals_file,
        model_provider="zhipu", embedding_provider="zhipu", rerank_provider="zhipu", zhipu_api_key=os.environ["ZHIPU_API_KEY"],
        chat_model=os.environ["CHAT_MODEL"], embedding_model=os.environ["EMBEDDING_MODEL"], dimensions=512)
    rt = Runtime(configured)
    try:
        seed(rt)
        result = rt.pipeline.run("退款金额超过多少元需要人工审核？", principal())
        assert result.outcome == "answered"
        assert result.citations and "2000" in result.text
    finally:
        rt.close()
