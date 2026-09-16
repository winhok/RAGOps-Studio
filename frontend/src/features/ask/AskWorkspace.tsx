import type { ChangeEvent, FormEvent } from 'react';
import type { ChatAnswer, DocumentRecord, Session, Trace } from '../../types';
import { label, Pill, sampleQuestions } from '../../ui';
import { Timeline } from '../traces/Timeline';

interface Props {
  session: Session;
  documents: DocumentRecord[];
  answer: ChatAnswer | null;
  trace: Trace | null;
  query: string;
  busy: boolean;
  onQueryChange: (value: string) => void;
  onSubmit: () => Promise<void>;
  onSampleSelect: (value: string) => void;
  onOpenSource: (documentId: string, version: number) => Promise<void>;
  onNavigateTrace: () => void;
}

function AnswerPanel({ answer, onNavigateTrace }: { answer: ChatAnswer; onNavigateTrace: () => void }) {
  return (
    <div className="panel answer-panel">
      <div className="panel-heading">
        <h3>Response</h3>
        <Pill type={answer.outcome === 'answered' ? 'green' : answer.outcome === 'refused' ? 'amber' : 'neutral'}>
          {answer.outcome}
        </Pill>
      </div>
      <div className="answer-text">{answer.text}</div>
      <div className="answer-meta">
        <span>{answer.search_attempts} retrieval round{answer.search_attempts === 1 ? '' : 's'}</span>
        <span>{answer.timings_ms.total.toFixed(0)} ms</span>
        <button className="text-button" onClick={onNavigateTrace}>Inspect trace ↗</button>
      </div>
      <div className="stop-reason">{label(answer.stop_reason)}</div>
    </div>
  );
}

function EvidenceColumn({ session, answer, onOpenSource }: Pick<Props, 'session' | 'answer' | 'onOpenSource'>) {
  const citations = answer?.citations ?? [];
  return (
    <aside className="evidence-column">
      <div className="panel">
        <div className="panel-heading">
          <h3>Bound sources</h3>
          <span className="counter">{citations.length}</span>
        </div>
        <p className="muted source-intro">Citations are resolved from stored chunks, not model-generated links.</p>
        {citations.length ? citations.map((citation, index) => (
          <button
            className="source-card"
            data-source={citation.document_id}
            data-version={citation.version}
            key={`${citation.document_id}-${citation.version}-${citation.chunk_id}`}
            onClick={() => void onOpenSource(citation.document_id, citation.version)}
          >
            <div className="source-top"><span className="source-number">{index + 1}</span><Pill>v{citation.version}</Pill></div>
            <strong>{citation.title}</strong>
            <small>{label(citation.evidence_type)}</small>
            <p>{citation.content.slice(0, 210)}{citation.content.length > 210 ? '…' : ''}</p>
            <span className="source-link">Open exact source ↗</span>
          </button>
        )) : (
          <div className="empty-sources"><span>▤</span><p>No citations yet.<br />Only verified evidence appears here.</p></div>
        )}
      </div>
      <div className="guard-card">
        <span>▣</span>
        <div>
          <strong>Access is checked before retrieval.</strong>
          <p>Your tenant, department and role are resolved on the server. Replaced or deleted versions cannot enter current answers.</p>
        </div>
      </div>
      {session.runtime.model_provider === 'local' ? (
        <div className="local-note">
          <strong>Local execution profile</strong>
          <p>Rule-based routing, feature hashing and extractive answers. No external model calls. Change the server configuration to use GLM / DeepSeek and model reranking.</p>
        </div>
      ) : null}
    </aside>
  );
}

export function AskWorkspace(props: Props) {
  const { session, documents, answer, trace, query, busy, onQueryChange, onSubmit, onSampleSelect, onOpenSource, onNavigateTrace } = props;
  const runtime = session.runtime;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void onSubmit();
  }

  return (
    <>
      <div className="page-heading">
        <div><span className="eyebrow">AGENTIC KNOWLEDGE WORKFLOW</span><h1>Answers you can audit.</h1><p>Ask a policy question. Inspect the decision, evidence and source.</p></div>
        <div className="heading-mark">◈</div>
      </div>
      <div className="stat-row">
        <div><span>Accessible documents</span><strong>{documents.length.toString().padStart(2, '0')}</strong></div>
        <div><span>Retrieval budget</span><strong>{runtime.max_searches}<small> rounds / request</small></strong></div>
        <div><span>Retrieval pipeline</span><strong className="stat-text">Dense + BM25 <small>→ RRF → {runtime.rerank_provider === 'zhipu' ? 'Model rerank' : 'Lexical rerank'}</small></strong></div>
      </div>
      <div className="ask-grid">
        <section>
          <div className="panel composer">
            <div className="panel-heading"><h3>Ask a question</h3><Pill type="green">Authenticated scope</Pill></div>
            <form id="query-form" onSubmit={submit}>
              <textarea id="query" maxLength={2000} rows={4} aria-label="Question" value={query} onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onQueryChange(event.target.value)} />
              <div className="composer-bottom">
                <span>⌕ &nbsp; {session.principal.tenant_id} / {session.principal.department_id}</span>
                <button className="button primary" disabled={busy}>{busy ? 'Searching & validating…' : 'Run query ↗'}</button>
              </div>
            </form>
          </div>
          <div className="sample-queries">
            {sampleQuestions.map(([title, value], index) => (
              <button key={title} data-question={index} onClick={() => onSampleSelect(value)} disabled={busy}>{title} <span>↗</span></button>
            ))}
          </div>
          {answer ? <AnswerPanel answer={answer} onNavigateTrace={onNavigateTrace} /> : (
            <div className="panel empty-answer"><span className="empty-symbol">⌁</span><h3>Your answer, with its evidence.</h3><p>The workflow can answer, ask for clarification,<br />or stop when current evidence is insufficient.</p></div>
          )}
          {trace ? <Timeline trace={trace} /> : null}
        </section>
        <EvidenceColumn session={session} answer={answer} onOpenSource={onOpenSource} />
      </div>
    </>
  );
}
