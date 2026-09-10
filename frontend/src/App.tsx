import { useMemo, useState } from 'react'
import {
  Activity,
  BookOpen,
  CheckCircle2,
  Database,
  FileSearch,
  Gauge,
  GitBranch,
  LockKeyhole,
  Search,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { chat, getTrace, ingestText, runEvaluation } from './api'
import type { ChatAnswer, Evaluation, Trace } from './types'

type Tab = 'chat' | 'documents' | 'evaluation' | 'trace'

const SAMPLE_QUESTIONS = [
  'How long do I have to return an unused product?',
  'When should support open a carrier investigation?',
  'Does cancelling Northstar Plus refund the current billing period?',
]

export function App() {
  const [tab, setTab] = useState<Tab>('chat')
  const [query, setQuery] = useState(SAMPLE_QUESTIONS[0])
  const [role, setRole] = useState('public')
  const [answer, setAnswer] = useState<ChatAnswer | null>(null)
  const [trace, setTrace] = useState<Trace | null>(null)
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const topRetrieval = useMemo(() => trace?.retrieval.slice(0, 5) ?? [], [trace])

  async function ask() {
    setBusy(true)
    setError('')
    try {
      const result = await chat(query, role)
      setAnswer(result)
      setTrace(await getTrace(result.trace_id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  async function evaluate() {
    setBusy(true)
    setError('')
    try {
      setEvaluation(await runEvaluation())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Evaluation failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><Sparkles size={20} /> RAGOps Studio</div>
        <p className="muted compact">Production RAG workbench</p>
        <nav>
          <NavButton active={tab === 'chat'} onClick={() => setTab('chat')} icon={<Search size={17} />} label="Ask & cite" />
          <NavButton active={tab === 'documents'} onClick={() => setTab('documents')} icon={<BookOpen size={17} />} label="Knowledge" />
          <NavButton active={tab === 'evaluation'} onClick={() => setTab('evaluation')} icon={<Gauge size={17} />} label="Evaluation" />
          <NavButton active={tab === 'trace'} onClick={() => setTab('trace')} icon={<Activity size={17} />} label="Trace inspector" />
        </nav>
        <div className="sidebar-card">
          <div><ShieldCheck size={16} /> Guardrails enabled</div>
          <small>ACL filter · citations · refusal route</small>
        </div>
      </aside>

      <main>
        <header>
          <div>
            <p className="eyebrow">HYBRID RETRIEVAL · RRF · RERANKING</p>
            <h1>{tab === 'chat' ? 'Grounded answers you can inspect' : tab === 'documents' ? 'Versioned knowledge base' : tab === 'evaluation' ? 'Measure retrieval quality' : 'Inspect every retrieval step'}</h1>
          </div>
          <span className="status"><span /> healthy</span>
        </header>

        {error && <div className="error">{error}</div>}
        {tab === 'chat' && (
          <section className="grid two">
            <div className="panel">
              <label>Question</label>
              <textarea value={query} onChange={(e) => setQuery(e.target.value)} rows={5} />
              <div className="row between">
                <select value={role} onChange={(e) => setRole(e.target.value)}>
                  <option value="public">public</option>
                  <option value="support">support</option>
                  <option value="admin">admin</option>
                </select>
                <button onClick={ask} disabled={busy}>{busy ? 'Running…' : 'Run RAG pipeline'}</button>
              </div>
              <div className="chips">
                {SAMPLE_QUESTIONS.map((item) => <button className="chip" key={item} onClick={() => setQuery(item)}>{item}</button>)}
              </div>
            </div>

            <div className="panel answer-panel">
              <div className="panel-title"><CheckCircle2 size={18} /> Grounded answer</div>
              {answer ? (
                <>
                  <p className="answer">{answer.text}</p>
                  <div className="metrics-row">
                    <Metric label="Confidence" value={`${Math.round(answer.confidence * 100)}%`} />
                    <Metric label="Route" value={answer.route} />
                    <Metric label="Latency" value={`${answer.timings_ms.total ?? 0} ms`} />
                  </div>
                  <h3>Citations</h3>
                  {answer.citations.map((citation) => (
                    <article className="citation" key={citation.chunk_id}>
                      <strong>{citation.title}</strong>
                      <span>{citation.source_id} · score {citation.score}</span>
                      <p>{citation.quote}</p>
                    </article>
                  ))}
                </>
              ) : <Empty icon={<FileSearch />} text="Run a query to see the answer, citations, confidence, and trace." />}
            </div>
          </section>
        )}

        {tab === 'documents' && <DocumentsPanel onDone={() => setTab('chat')} />}

        {tab === 'evaluation' && (
          <section className="panel">
            <div className="row between">
              <div>
                <div className="panel-title"><Gauge size={18} /> Offline benchmark</div>
                <p className="muted">Runs the included synthetic support benchmark and reports retrieval metrics.</p>
              </div>
              <button onClick={evaluate} disabled={busy}>{busy ? 'Evaluating…' : 'Run benchmark'}</button>
            </div>
            {evaluation ? (
              <div className="metric-grid">
                <BigMetric label="Recall@5" value={evaluation.summary.recall_at_k} />
                <BigMetric label="MRR" value={evaluation.summary.mrr} />
                <BigMetric label="nDCG@5" value={evaluation.summary.ndcg_at_k} />
                <BigMetric label="Keyword coverage" value={evaluation.summary.keyword_coverage} />
              </div>
            ) : <Empty icon={<GitBranch />} text="No benchmark run in this browser session yet." />}
          </section>
        )}

        {tab === 'trace' && (
          <section className="panel">
            <div className="panel-title"><Activity size={18} /> Retrieval trace</div>
            {trace ? (
              <>
                <div className="trace-meta">
                  <span>{trace.trace_id}</span><span>role: {trace.role}</span><span>route: {trace.route}</span>
                </div>
                <div className="trace-table">
                  <div className="trace-head"><span>Source</span><span>Dense</span><span>BM25</span><span>RRF</span><span>Rerank</span></div>
                  {topRetrieval.map((row) => (
                    <div className="trace-row" key={row.chunk_id}>
                      <span><Database size={14} /> {row.source_id}</span>
                      <span>{row.dense_score.toFixed(3)}</span>
                      <span>{row.lexical_score.toFixed(3)}</span>
                      <span>{row.rrf_score.toFixed(4)}</span>
                      <span>{row.rerank_score.toFixed(3)}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : <Empty icon={<Activity />} text="Run a query first; its retrieval trace will appear here." />}
          </section>
        )}
      </main>
    </div>
  )
}

function NavButton({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return <button className={active ? 'nav active' : 'nav'} onClick={onClick}>{icon}{label}</button>
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>
}

function BigMetric({ label, value }: { label: string; value: number }) {
  return <div className="big-metric"><span>{label}</span><strong>{(value * 100).toFixed(1)}%</strong></div>
}

function Empty({ icon, text }: { icon: React.ReactNode; text: string }) {
  return <div className="empty">{icon}<p>{text}</p></div>
}

function DocumentsPanel({ onDone }: { onDone: () => void }) {
  const [sourceId, setSourceId] = useState('custom-policy')
  const [title, setTitle] = useState('Custom Policy')
  const [content, setContent] = useState('Paste at least a few sentences of policy text here. Re-ingesting the same source with changed content creates a new active version.')
  const [role, setRole] = useState('public')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit() {
    setBusy(true)
    try {
      await ingestText({ source_id: sourceId, title, content, allowed_roles: [role] })
      setMessage('Ingested. If this source existed, the previous version is now inactive.')
      setTimeout(onDone, 800)
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="grid two">
      <div className="panel">
        <div className="panel-title"><BookOpen size={18} /> Ingest text</div>
        <label>Source ID</label><input value={sourceId} onChange={(e) => setSourceId(e.target.value)} />
        <label>Title</label><input value={title} onChange={(e) => setTitle(e.target.value)} />
        <label>Allowed role</label><select value={role} onChange={(e) => setRole(e.target.value)}><option>public</option><option>support</option><option>admin</option></select>
        <label>Content</label><textarea rows={10} value={content} onChange={(e) => setContent(e.target.value)} />
        <button onClick={submit} disabled={busy}>{busy ? 'Ingesting…' : 'Create new version'}</button>
        {message && <p className="muted">{message}</p>}
      </div>
      <div className="panel">
        <div className="panel-title"><LockKeyhole size={18} /> Production behaviors</div>
        <ul className="feature-list">
          <li>SHA-256 duplicate detection</li>
          <li>Logical source versioning with one active version</li>
          <li>Role-aware retrieval before ranking</li>
          <li>Hybrid BM25 + dense retrieval</li>
          <li>RRF fusion + reranking</li>
          <li>Citations, confidence, and refusal route</li>
          <li>Trace-level component scores and latency</li>
        </ul>
      </div>
    </section>
  )
}
