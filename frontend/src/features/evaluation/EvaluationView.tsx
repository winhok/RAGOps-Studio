import type { Evaluation, Session } from '../../types';
import { Pill } from '../../ui';

interface Props {
  session: Session;
  evaluation: Evaluation | null;
  busy: boolean;
  onRun: () => Promise<void>;
  onOpenTrace: (traceId: string) => Promise<void>;
}

export function EvaluationView({ session, evaluation, busy, onRun, onOpenTrace }: Props) {
  const isAdmin = session.principal.role === 'admin';
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">QUALITY REGRESSION</span>
          <h1>Evaluate the retrieval path.</h1>
          <p>Repeatable checks against a small, synthetic policy corpus.</p>
        </div>
        {isAdmin ? (
          <button className="button primary" data-action="evaluate" onClick={() => void onRun()} disabled={busy}>{busy ? 'Running…' : 'Run regression ↗'}</button>
        ) : <Pill>Administrator access required</Pill>}
      </div>
      <div className="banner neutral">These results measure the bundled synthetic cases. They are not production accuracy or an answer-faithfulness score.</div>
      {evaluation ? (
        <>
          <div className="stat-row eval-stats">
            {[
              ['Recall@' + evaluation.k, evaluation.summary.recall_at_k],
              ['MRR', evaluation.summary.mrr],
              ['nDCG@' + evaluation.k, evaluation.summary.ndcg_at_k],
              ['Keyword coverage', evaluation.summary.keyword_coverage],
            ].map(([name, value]) => (
              <div key={String(name)}><span>{name}</span><strong>{(Number(value) * 100).toFixed(1)}<small>%</small></strong></div>
            ))}
          </div>
          <div className="panel">
            <div className="panel-heading"><h3>{evaluation.summary.cases} evaluated questions</h3><Pill>{evaluation.runtime.model_provider}</Pill></div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Question</th><th>Outcome</th><th>Recall</th><th>MRR</th><th /></tr></thead>
                <tbody>
                  {evaluation.cases.map((item) => (
                    <tr key={item.trace_id}>
                      <td className="eval-question">{item.query}</td>
                      <td><Pill type={item.outcome === 'answered' ? 'green' : 'neutral'}>{item.outcome}</Pill></td>
                      <td>{item.recall_at_k.toFixed(2)}</td>
                      <td>{item.reciprocal_rank.toFixed(2)}</td>
                      <td><button className="text-button" data-trace={item.trace_id} onClick={() => void onOpenTrace(item.trace_id)}>Trace ↗</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <p className="muted">{evaluation.metric_scope}</p>
        </>
      ) : (
        <div className="panel empty-answer"><span className="empty-symbol">◫</span><h3>A baseline, not a vanity metric.</h3><p>Run the existing evaluation suite to inspect document-level<br />Recall@K, MRR, nDCG@K and keyword coverage.</p></div>
      )}
    </>
  );
}
