from __future__ import annotations

"""LangGraph orchestration wrapper with a deterministic fallback for zero-key demos.

When `langgraph` is installed (as declared in requirements.txt), the API runs through
an explicit StateGraph. The tiny fallback keeps core tests and source checkouts usable
in constrained environments where optional runtime dependencies are not installed.
"""

from dataclasses import asdict
from typing import TypedDict

from app.services.pipeline import RAGPipeline


class GraphState(TypedDict, total=False):
    query: str
    role: str
    top_k: int
    result: dict


class _FallbackGraph:
    def __init__(self, pipeline: RAGPipeline) -> None:
        self.pipeline = pipeline

    def invoke(self, state: GraphState) -> GraphState:
        answer = self.pipeline.run(
            state["query"],
            role=state.get("role", "public"),
            top_k=state.get("top_k", 5),
        )
        return {**state, "result": asdict(answer)}


def build_rag_graph(pipeline: RAGPipeline):
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:
        return _FallbackGraph(pipeline)

    graph = StateGraph(GraphState)

    def execute(state: GraphState) -> GraphState:
        answer = pipeline.run(
            state["query"],
            role=state.get("role", "public"),
            top_k=state.get("top_k", 5),
        )
        return {**state, "result": asdict(answer)}

    graph.add_node("rag_pipeline", execute)
    graph.add_edge(START, "rag_pipeline")
    graph.add_edge("rag_pipeline", END)
    return graph.compile()
