from __future__ import annotations
import logging
import time
import uuid
from dataclasses import asdict
from app.core.errors import AppError, ProviderError
from app.core.models import Answer, Principal
from app.services.graph import WorkflowNodes, build_rag_graph, initial_state
logger = logging.getLogger(__name__)

class RAGPipeline:

    def __init__(self, store, settings, retriever, models):
        self.store, self.settings, self.retriever, self.models = (store, settings, retriever, models)

    def run(self, query: str, principal: Principal, top_k: int=4) -> Answer:
        trace_id = f'tr_{uuid.uuid4().hex}'
        started = time.perf_counter()
        state = initial_state(query)
        nodes = None
        try:
            nodes = WorkflowNodes(self.models, self.retriever, principal, self.store, max_searches=self.settings.max_searches, top_k=top_k, use_langchain=self.settings.graph_engine == 'langgraph')
            graph = build_rag_graph(nodes, self.settings.graph_engine)
            state = graph.invoke(state)
            timings = {**state['timings_ms'], 'total': round((time.perf_counter() - started) * 1000, 2)}
            answer = Answer(text=state['text'], citations=state['citations'], trace_id=trace_id, outcome=state['outcome'], route=state['route'], search_attempts=state['search_attempts'], required_evidence=state['required_evidence'], missing_evidence=state['missing_evidence'], stop_reason=state['stop_reason'], timings_ms=timings, runtime=self.settings.public_runtime())
            self.store.save_trace(principal, trace_id, {'trace_id': trace_id, 'query': query, 'outcome': answer.outcome, 'route': answer.route, 'search_attempts': answer.search_attempts, 'required_evidence': answer.required_evidence, 'missing_evidence': answer.missing_evidence, 'stop_reason': answer.stop_reason, 'timings_ms': timings, 'events': state['events'], 'searches': state['searches'], 'rejected': state['rejected'], 'answer': answer.text, 'citations': answer.citations, 'cited_ids': [c['chunk_id'] for c in answer.citations], 'runtime': answer.runtime})
            logger.info('rag_completed', extra={'trace_id': trace_id, 'outcome': answer.outcome, 'latency_ms': timings['total']})
            return answer
        except Exception as exc:
            if nodes is not None and nodes.last_state is not None:
                state = nodes.last_state
            code = exc.code if isinstance(exc, AppError) else 'workflow_failure'
            self.store.save_trace(principal, trace_id, {'trace_id': trace_id, 'query': query, 'outcome': 'failed', 'error_code': code, 'events': state['events'], 'searches': state['searches'], 'citations': [], 'cited_ids': [], 'timings_ms': {'total': round((time.perf_counter() - started) * 1000, 2)}, 'runtime': self.settings.public_runtime()})
            logger.warning('rag_failed', extra={'trace_id': trace_id, 'error_code': code})
            if isinstance(exc, AppError):
                exc.trace_id = trace_id
                raise
            raise ProviderError('Workflow failed safely; no answer or source was released', trace_id=trace_id) from exc
