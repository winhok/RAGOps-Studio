from __future__ import annotations
import time
from dataclasses import asdict
from datetime import datetime
from typing import TypedDict
from pydantic import BaseModel, ConfigDict, Field
from app.core.auth import can_read
from app.core.errors import ConfigurationError
from app.core.models import Decision, EvidenceType, GroundedAnswer, Principal, utcnow
from app.services.retrieval import hit_record
from app.services.store import valid_dates
from app.services.vector_index import permission_filter
QUERY_HINTS = {'review_rule': '当前退款金额人工审核阈值 refund amount manual review threshold', 'material_requirement': '咖啡机申请退款材料订单号序列号照片 refund required documents serial number', 'arrival_rule': '退款审核通过后到账时间 refund arrival business days', 'maintenance_policy': '终身免费上门保养 maintenance lifetime service policy', 'finance_policy': '财务对账大额退款资金复核 finance refund review original payment history', 'service_workflow': '客服人工审核流程初审 support manual review workflow', 'promotion_policy': '企业活动优惠券 promotion discount policy', 'general': ''}

class SearchArguments(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: str = Field(min_length=1, max_length=3000)
    evidence_type: EvidenceType

class RetrievalTool:
    """The trusted principal is bound at construction, never exposed as a tool argument."""
    name = 'search_knowledge'
    args_schema = SearchArguments

    def __init__(self, retriever, principal: Principal, top_k: int, use_langchain: bool=False):

        def search(query: str, evidence_type: EvidenceType):
            return retriever.retrieve(query, principal, evidence_type, top_k)
        self.search = search
        self.langchain_tool = None
        if use_langchain:
            try:
                from langchain_core.tools import StructuredTool
            except ImportError as exc:
                raise ConfigurationError('Install LangChain integration requirements') from exc
            self.langchain_tool = StructuredTool.from_function(search, name=self.name, description='Retrieve one missing evidence type from the current authorized knowledge base.', args_schema=SearchArguments)

    def invoke(self, arguments: dict):
        data = self.args_schema.model_validate(arguments).model_dump()
        return self.langchain_tool.invoke(data) if self.langchain_tool else self.search(**data)

class GraphState(TypedDict, total=False):
    query: str
    route: str
    required_evidence: list[str]
    clarification_question: str | None
    candidates: list
    usable: list
    rejected: list[dict]
    missing_evidence: list[str]
    searched_types: list[str]
    search_attempts: int
    events: list[dict]
    searches: list[dict]
    timings_ms: dict[str, float]
    text: str
    citations: list[dict]
    outcome: str
    stop_reason: str

def initial_state(query: str) -> GraphState:
    return dict(query=query, route='', required_evidence=[], clarification_question=None, candidates=[], usable=[], rejected=[], missing_evidence=[], searched_types=[], search_attempts=0, events=[], searches=[], timings_ms={}, text='', citations=[], outcome='', stop_reason='')

class WorkflowNodes:

    def __init__(self, models, retriever, principal: Principal, store, *, max_searches=3, top_k=4, now=None, use_langchain=False):
        self.models, self.principal, self.store = (models, principal, store)
        self.max_searches = max_searches
        self.now = now or utcnow
        self.last_state = None
        self.tool = RetrievalTool(retriever, principal, top_k, use_langchain)

    def run_node(self, name, state):
        patch = getattr(self, name)(state)
        self.last_state = {**state, **patch}
        return patch

    @staticmethod
    def event(state, node, message, **fields):
        return [*state['events'], {'node': node, 'message': message, **fields}]

    def decide_request(self, state):
        started = time.perf_counter()
        decision = Decision.model_validate(self.models.decide(state['query']))
        return {'route': decision.route, 'required_evidence': decision.required_evidence, 'missing_evidence': decision.required_evidence, 'clarification_question': decision.clarification_question, 'events': self.event(state, 'decide_request', decision.reason, route=decision.route), 'timings_ms': {**state['timings_ms'], 'decision': round((time.perf_counter() - started) * 1000, 2)}}

    def search_knowledge(self, state):
        evidence_type = state['missing_evidence'][0]
        query = (QUERY_HINTS[evidence_type] + '。 ' + state['query']).strip()
        hits, timing, scope_count = self.tool.invoke({'query': query, 'evidence_type': evidence_type})
        by_id = {h.chunk.id: h for h in state['candidates']}
        for hit in hits:
            # Fail closed even when an alternative backend violates its filtering contract.
            c = hit.chunk
            if not can_read(self.principal, c.tenant_id, c.department_id, c.visibility):
                continue
            by_id[c.id] = hit
        visible = [h for h in hits if can_read(self.principal, h.chunk.tenant_id, h.chunk.department_id, h.chunk.visibility)]
        record = {'attempt': state['search_attempts'] + 1, 'evidence_type': evidence_type, 'query': query, 'scope_count': scope_count, 'permission_filter': permission_filter(self.principal) + ' and [current revision allow-list]', 'timings_ms': timing, 'candidates': [hit_record(h) for h in visible]}
        return {'search_attempts': state['search_attempts'] + 1, 'searched_types': [*state['searched_types'], evidence_type], 'candidates': list(by_id.values()), 'searches': [*state['searches'], record], 'events': self.event(state, 'search_knowledge', f'Retrieved {len(visible)} candidates for {evidence_type}', evidence_type=evidence_type)}

    def assess_evidence(self, state):
        usable, rejected = ([], [])
        now = self.now()
        for hit in state['candidates']:
            c = hit.chunk
            if not can_read(self.principal, c.tenant_id, c.department_id, c.visibility):
                continue
            reason = None
            if not c.active:
                reason = 'inactive_revision'
            elif not valid_dates(c.effective_at, c.expires_at, now):
                reason = 'not_yet_effective_or_expired'
            elif not c.evidence_types().intersection(state['required_evidence']) and 'general' not in state['required_evidence']:
                reason = 'unrequested_evidence_type'
            if reason:
                rejected.append({'chunk_id': c.id, 'reason': reason})
            else:
                usable.append(hit)
        available = {kind for h in usable for kind in h.chunk.evidence_types()}
        missing = [kind for kind in state['required_evidence'] if kind not in available and (not (kind == 'general' and usable))]
        return {'usable': usable, 'rejected': rejected, 'missing_evidence': missing, 'events': self.event(state, 'assess_evidence', 'Missing: ' + ', '.join(missing) if missing else 'All required evidence types are present', missing=missing, rejected_count=len(rejected))}

    def after_assessment(self, state):
        if not state['missing_evidence']:
            return 'generate_answer'
        if state['search_attempts'] >= self.max_searches:
            return 'refuse_answer'
        if state['missing_evidence'][0] in state['searched_types']:
            return 'refuse_answer'
        return 'search_knowledge'

    def generate_answer(self, state):
        started = time.perf_counter()
        evidence = [h.chunk for h in state['usable']]
        response = GroundedAnswer.model_validate(self.models.answer(state['query'], evidence))
        allowed = {c.id: c for c in evidence}
        ids = list(dict.fromkeys(response.source_ids))
        reason = ''
        if response.status != 'answered':
            reason = 'model_refused'
        elif not ids or any((cid not in allowed for cid in ids)):
            reason = 'invalid_source_ids'
        else:
            types = {kind for cid in ids for kind in allowed[cid].evidence_types()}
            if any((kind != 'general' and kind not in types for kind in state['required_evidence'])):
                reason = 'missing_citation_types'
            elif not set(ids) <= self.store.current_ids(self.principal):
                reason = 'source_changed_during_generation'
        timings = {**state['timings_ms'], 'generation': round((time.perf_counter() - started) * 1000, 2)}
        if reason:
            return {'outcome': 'refused', 'text': '当前资料不足，或答案未通过来源校验；本次不返回未经支持的业务结论。 / The answer could not be verified against current authorized sources.', 'citations': [], 'stop_reason': reason, 'timings_ms': timings, 'events': self.event(state, 'validate_sources', reason)}
        citations = []
        for cid in ids:
            c = allowed[cid]
            citations.append({'chunk_id': c.id, 'document_id': c.document_id, 'title': c.title, 'version': c.version, 'chunk_index': c.index, 'evidence_type': c.evidence_type, 'content': c.text, 'source_path': c.source_path, 'source_url': f'/api/documents/{c.document_id}/versions/{c.version}/source'})
        return {'outcome': 'answered', 'text': response.answer, 'citations': citations, 'stop_reason': 'evidence_complete', 'timings_ms': timings, 'events': self.event(state, 'validate_sources', f'Bound {len(citations)} citations to current source records')}

    def direct_answer(self, state):
        return {'outcome': 'direct', 'text': self.models.direct(state['query']), 'citations': [], 'stop_reason': 'no_retrieval_needed', 'events': self.event(state, 'direct_answer', 'Completed without accessing the knowledge base')}

    def clarify_user(self, state):
        return {'outcome': 'clarify', 'text': state['clarification_question'], 'citations': [], 'stop_reason': 'missing_user_input', 'events': self.event(state, 'clarify_user', 'Requested the minimum missing user input')}

    def refuse_answer(self, state):
        reason = 'search_budget_exhausted' if state['search_attempts'] >= self.max_searches else 'no_new_evidence'
        return {'outcome': 'refused', 'text': '当前有效且有权限的知识库资料不足，无法回答这个问题。 / There is not enough current, authorized evidence to answer this question.', 'citations': [], 'stop_reason': reason, 'events': self.event(state, 'refuse_answer', reason, missing=state['missing_evidence'])}

    @staticmethod
    def after_decision(state):
        return {'direct': 'direct_answer', 'clarify': 'clarify_user', 'retrieve': 'search_knowledge'}[state['route']]

class PythonWorkflow:
    """Explicit bounded state-machine runner; uses the same nodes as the LangGraph adapter."""

    def __init__(self, nodes: WorkflowNodes):
        self.nodes = nodes

    def invoke(self, state: GraphState):
        current = 'decide_request'
        for _ in range(2 * self.nodes.max_searches + 5):
            state = {**state, **self.nodes.run_node(current, state)}
            if current == 'decide_request':
                current = self.nodes.after_decision(state)
            elif current == 'search_knowledge':
                current = 'assess_evidence'
            elif current == 'assess_evidence':
                current = self.nodes.after_assessment(state)
            else:
                return state
        raise RuntimeError('Workflow exceeded its bounded node budget')

def build_rag_graph(nodes: WorkflowNodes, engine: str):
    if engine == 'python':
        return PythonWorkflow(nodes)
    if engine != 'langgraph':
        raise ConfigurationError('Unknown graph engine')
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise ConfigurationError('LangGraph is selected but not installed. Install requirements-integrations.txt; no fallback was used.') from exc
    graph = StateGraph(GraphState)
    for name in ('decide_request', 'search_knowledge', 'assess_evidence', 'generate_answer', 'direct_answer', 'clarify_user', 'refuse_answer'):
        graph.add_node(name, lambda state, name=name: nodes.run_node(name, state))
    graph.add_edge(START, 'decide_request')
    graph.add_conditional_edges('decide_request', nodes.after_decision, {'direct_answer': 'direct_answer', 'clarify_user': 'clarify_user', 'search_knowledge': 'search_knowledge'})
    graph.add_edge('search_knowledge', 'assess_evidence')
    graph.add_conditional_edges('assess_evidence', nodes.after_assessment, {'generate_answer': 'generate_answer', 'refuse_answer': 'refuse_answer', 'search_knowledge': 'search_knowledge'})
    for name in ('generate_answer', 'direct_answer', 'clarify_user', 'refuse_answer'):
        graph.add_edge(name, END)
    return graph.compile()
