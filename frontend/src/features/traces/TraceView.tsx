import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react';
import type { Trace } from '../../types';
import { label, Pill, score } from '../../ui';
import { Timeline } from './Timeline';

interface Props {
  trace: Trace | null;
  busy: boolean;
  onLoadTrace: (traceId: string) => Promise<void>;
}

export function TraceView({ trace, busy, onLoadTrace }: Props) {
  const [traceId, setTraceId] = useState(trace?.trace_id ?? '');

  useEffect(() => {
    if (trace?.trace_id) setTraceId(trace.trace_id);
  }, [trace?.trace_id]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = traceId.trim();
    if (value && !busy) void onLoadTrace(value);
  }

  return (
    <>
      <div className="page-heading">
        <div><span className="eyebrow">RETRIEVAL OBSERVABILITY</span><h1>Execution traces</h1><p>Follow every decision, search round and citation check.</p></div>
      </div>
      <form id="trace-form" className="trace-search" onSubmit={submit}>
        <input aria-label="Trace ID" placeholder="Enter a trace ID" value={traceId} onChange={(event: ChangeEvent<HTMLInputElement>) => setTraceId(event.target.value)} required />
        <button className="button secondary" disabled={busy}>Load trace</button>
      </form>
      {trace ? (
        <>
          <div className="stat-row">
            <div><span>Outcome</span><strong className="stat-text">{trace.outcome}</strong></div>
            <div><span>Search rounds</span><strong>{trace.search_attempts ?? 0}</strong></div>
            <div><span>Total latency</span><strong>{trace.timings_ms.total.toFixed(0)}<small> ms</small></strong></div>
          </div>
          <p className="trace-question">{trace.query}</p>
          <Timeline trace={trace} />
          {trace.searches.map((round) => (
            <div className="panel round" key={`${round.attempt}-${round.evidence_type}`}>
              <div className="panel-heading">
                <h3>Round {round.attempt} <span className="muted">/ {label(round.evidence_type)}</span></h3>
                <Pill>{round.candidates.length} candidates</Pill>
              </div>
              <div className="filter-line"><span>SERVER FILTER</span><code>{round.permission_filter}</code></div>
              <div className="round-query">{round.query}</div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Candidate</th><th>Dense</th><th>BM25</th><th>RRF</th><th>Rerank</th></tr></thead>
                  <tbody>
                    {round.candidates.length ? round.candidates.map((candidate) => (
                      <tr key={candidate.chunk_id}>
                        <td><strong>{candidate.title}</strong><small className="block mono">{candidate.chunk_id.slice(0, 21)}… · v{candidate.version}</small></td>
                        <td>{score(candidate.dense_score)}</td>
                        <td>{score(candidate.lexical_score)}</td>
                        <td>{score(candidate.rrf_score)}</td>
                        <td><strong>{score(candidate.rerank_score)}</strong></td>
                      </tr>
                    )) : <tr><td colSpan={5} className="empty-cell">No candidates in this authorized scope.</td></tr>}
                  </tbody>
                </table>
              </div>
              <div className="stage-timings">
                {Object.entries(round.timings_ms).map(([name, value]) => <span key={name}>{name} <b>{value.toFixed(1)} ms</b></span>)}
              </div>
            </div>
          ))}
          {trace.rejected?.length ? (
            <div className="panel rejected">
              <h3>Rejected evidence</h3>
              {trace.rejected.map((entry) => <p key={`${entry.chunk_id}-${entry.reason}`}><code>{entry.chunk_id}</code> · {label(entry.reason)}</p>)}
            </div>
          ) : null}
          <p className="muted">A dash means the backend did not report that individual score. It is not a zero or an estimated value.</p>
        </>
      ) : (
        <div className="panel empty-answer"><h3>No trace selected</h3><p>Run a question, or load an authorized trace ID.</p></div>
      )}
    </>
  );
}
