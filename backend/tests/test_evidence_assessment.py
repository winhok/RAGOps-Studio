import pytest

from app.core.errors import ProviderError
from app.core.models import Decision, EvidenceAssessment, RetrievalHit, SearchRevision
from app.services.graph import WorkflowNodes, build_rag_graph, initial_state
from app.services.providers import LocalModels


class ControlledAssessment(LocalModels):
    """Controlled judgment outcomes test workflow contracts, not model accuracy."""
    def decide(self, question):
        return Decision(route='retrieve', required_evidence=['general'], reason='Document question')

    def assess(self, question, evidence):
        return EvidenceAssessment(relevant_ids=[c.id for c in evidence if c.document_id == 'retention'])

    def revise_search(self, question, previous_query):
        return SearchRevision(query='uploaded document retention period')


def topic_sources(runtime, admin, publish):
    publish(id='travel', title='Travel expenses', evidence_type='general', content='Uploaded documents for business travel must include meal receipts.')
    publish(id='retention', title='Document retention', evidence_type='general', content='Uploaded documents are retained for 30 days.')
    return {c.document_id: c for c in runtime.store.snapshot(admin)}


@pytest.mark.parametrize('engine', ['python', 'langgraph'])
def test_irrelevant_shared_keywords_trigger_one_revision_then_grounded_answer(runtime, admin, publish, monkeypatch, engine):
    if engine == 'langgraph':
        pytest.importorskip('langgraph.graph')
        pytest.importorskip('langchain_core.tools')
    sources = topic_sources(runtime, admin, publish)
    original = runtime.retriever.retrieve
    queries = []
    def retrieve(query, *args):
        queries.append(query)
        if len(queries) == 1:
            return [RetrievalHit(sources['travel'], 0.9)], {}, 2
        return original(query, *args)
    monkeypatch.setattr(runtime.retriever, 'retrieve', retrieve)
    nodes = WorkflowNodes(ControlledAssessment(), runtime.retriever, admin, runtime.store, use_langchain=engine == 'langgraph')
    result = build_rag_graph(nodes, engine).invoke(initial_state('How long do you retain uploaded documents?'))
    assert result['outcome'] == 'answered'
    assert len(queries) == result['search_attempts'] == 2
    assert queries[0] != queries[1]
    assert {c['document_id'] for c in result['citations']} == {'retention'}
    assert result['searches'][0]['assessment']['status'] == 'insufficient'
    assert result['searches'][1]['assessment']['status'] == 'supporting'
    assert any(r['chunk_id'] == sources['travel'].id and r['reason'] == 'not_relevant_to_question' for r in result['rejected'])
    assert [e['node'] for e in result['events']].count('revise_search') == 1


def test_revision_is_counted_in_search_budget(runtime, admin, publish, monkeypatch):
    sources = topic_sources(runtime, admin, publish)
    monkeypatch.setattr(runtime.retriever, 'retrieve', lambda *args: ([RetrievalHit(sources['travel'], 0.9)], {}, 2))
    runtime.pipeline.models = ControlledAssessment()
    runtime.settings.max_searches = 1
    result = runtime.pipeline.run('How long do you retain uploaded documents?', admin)
    assert result.outcome == 'refused' and result.stop_reason == 'search_budget_exhausted'
    assert result.search_attempts == 1 and not result.citations
    assert not any(e['node'] == 'revise_search' for e in runtime.store.get_trace(admin, result.trace_id)['events'])


def test_still_irrelevant_after_revision_stops_without_generation(runtime, admin, publish, monkeypatch):
    sources = topic_sources(runtime, admin, publish)
    monkeypatch.setattr(runtime.retriever, 'retrieve', lambda *args: ([RetrievalHit(sources['travel'], 0.9)], {}, 2))
    models = ControlledAssessment()
    monkeypatch.setattr(models, 'answer', lambda *args: pytest.fail('Irrelevant evidence reached generation'))
    runtime.pipeline.models = models
    runtime.settings.max_searches = 8
    result = runtime.pipeline.run('How long do you retain uploaded documents?', admin)
    assert result.outcome == 'refused' and result.search_attempts == 2
    assert result.stop_reason == 'no_new_evidence'


def test_equivalent_revision_is_not_searched_again(runtime, admin, publish, monkeypatch):
    sources = topic_sources(runtime, admin, publish)
    monkeypatch.setattr(runtime.retriever, 'retrieve', lambda *args: ([RetrievalHit(sources['travel'], 0.9)], {}, 2))
    models = ControlledAssessment()
    monkeypatch.setattr(models, 'revise_search', lambda question, previous: SearchRevision(query=previous.upper() + ' ?'))
    runtime.pipeline.models = models
    result = runtime.pipeline.run('Retention period?', admin)
    assert result.outcome == 'refused' and result.search_attempts == 1
    trace = runtime.store.get_trace(admin, result.trace_id)
    assert 'no distinct alternative' in trace['events'][-2]['message']


def test_assessment_cannot_invent_sources(runtime, admin, publish, monkeypatch):
    publish()
    models = LocalModels()
    monkeypatch.setattr(models, 'assess', lambda *args: EvidenceAssessment(relevant_ids=['invented']))
    runtime.pipeline.models = models
    with pytest.raises(ProviderError) as error:
        runtime.pipeline.run('Refund threshold?', admin)
    trace = runtime.store.get_trace(admin, error.value.trace_id)
    assert trace['outcome'] == 'failed' and trace['citations'] == []
    assert len(trace['searches']) == 1


def test_assessment_failure_does_not_release_unchecked_answer(runtime, admin, publish, monkeypatch):
    publish()
    models = LocalModels()
    def fail(*args):
        raise ProviderError('Assessment unavailable')
    monkeypatch.setattr(models, 'assess', fail)
    monkeypatch.setattr(models, 'answer', lambda *args: pytest.fail('Assessment failure reached generation'))
    runtime.pipeline.models = models
    with pytest.raises(ProviderError) as error:
        runtime.pipeline.run('Refund threshold?', admin)
    trace = runtime.store.get_trace(admin, error.value.trace_id)
    assert trace['error_code'] == 'provider_error'
    assert len(trace['searches']) == 1 and trace['citations'] == []


def test_revoked_source_is_removed_before_model_assessment(runtime, admin, publish, monkeypatch):
    publish()
    original = runtime.retriever.retrieve
    def revoke(*args):
        result = original(*args)
        runtime.store.delete(admin, 'policy', 1)
        return result
    monkeypatch.setattr(runtime.retriever, 'retrieve', revoke)
    models = LocalModels()
    monkeypatch.setattr(models, 'assess', lambda *args: pytest.fail('Revoked source reached assessment'))
    runtime.pipeline.models = models
    result = runtime.pipeline.run('Refund threshold?', admin)
    assert result.outcome == 'refused'


def test_empty_authorized_scope_does_not_rewrite_or_assess(runtime, admin, monkeypatch):
    models = LocalModels()
    monkeypatch.setattr(models, 'assess', lambda *args: pytest.fail('No authorized evidence'))
    monkeypatch.setattr(models, 'revise_search', lambda *args: pytest.fail('No authorized scope'))
    runtime.pipeline.models = models
    result = runtime.pipeline.run('Refund threshold?', admin)
    assert result.outcome == 'refused' and result.search_attempts == 1
