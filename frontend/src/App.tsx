import { useCallback, useEffect, useRef, useState, type MouseEvent } from 'react';
import { api, ApiError, hasCredential, setCredential as persistCredential } from './api';
import type { ChatAnswer, DocumentRecord, Evaluation, Session, Trace } from './types';
import type { ModalState } from './modalTypes';
import { Feedback, icons, labels, Pill, sampleQuestions, type Tab } from './ui';
import { LoginPage } from './features/auth/LoginPage';
import { AskWorkspace } from './features/ask/AskWorkspace';
import { KnowledgeLibrary } from './features/documents/KnowledgeLibrary';
import { TraceView } from './features/traces/TraceView';
import { EvaluationView } from './features/evaluation/EvaluationView';
import { DocumentModal } from './features/documents/DocumentModal';

const initialQuery = sampleQuestions[0][1];

function formatError(error: unknown) {
  let message = error instanceof Error ? error.message : 'Request failed';
  if (error instanceof ApiError && error.traceId) message += ` · Trace ${error.traceId}`;
  return message;
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [tab, setTab] = useState<Tab>('ask');
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [answer, setAnswer] = useState<ChatAnswer | null>(null);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [query, setQuery] = useState<string>(initialQuery);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [modal, setModal] = useState<ModalState>(null);
  const epochRef = useRef(0);
  const connectingRef = useRef(false);

  const runTask = useCallback(async (work: () => Promise<void>) => {
    if (busy) return;
    const epoch = epochRef.current;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await work();
    } catch (caught) {
      if (epoch !== epochRef.current) return;
      setError(formatError(caught));
    } finally {
      if (epoch === epochRef.current) setBusy(false);
    }
  }, [busy]);

  const loadDocuments = useCallback(async () => {
    const result = await api<DocumentRecord[]>('/api/documents');
    setDocuments(result);
  }, []);

  const connectWithStoredCredential = useCallback(async () => {
    if (connectingRef.current) return;
    connectingRef.current = true;
    setBusy(true);
    setError('');
    try {
      const [nextSession, nextDocuments] = await Promise.all([
        api<Session>('/api/session'),
        api<DocumentRecord[]>('/api/documents'),
      ]);
      setSession(nextSession);
      setDocuments(nextDocuments);
    } catch (caught) {
      persistCredential('');
      setSession(null);
      setDocuments([]);
      setError(caught instanceof Error ? caught.message : 'Unable to connect');
    } finally {
      connectingRef.current = false;
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (hasCredential()) void connectWithStoredCredential();
  }, [connectWithStoredCredential]);

  const connect = useCallback(async (credential: string) => {
    persistCredential(credential);
    await connectWithStoredCredential();
  }, [connectWithStoredCredential]);

  const signOut = useCallback(() => {
    if (busy) return;
    epochRef.current += 1;
    persistCredential('');
    setSession(null);
    setTab('ask');
    setDocuments([]);
    setAnswer(null);
    setTrace(null);
    setEvaluation(null);
    setModal(null);
    setQuery(initialQuery);
    setError('');
    setNotice('');
    setBusy(false);
  }, [busy]);

  const runQuery = useCallback(async () => {
    const normalized = query.trim();
    if (!normalized || busy) return;
    setAnswer(null);
    setTrace(null);
    await runTask(async () => {
      const nextAnswer = await api<ChatAnswer>('/api/chat', {
        method: 'POST',
        body: JSON.stringify({ query: normalized, top_k: 4 }),
      });
      setAnswer(nextAnswer);
      setTrace(await api<Trace>(`/api/traces/${encodeURIComponent(nextAnswer.trace_id)}`));
    });
  }, [busy, query, runTask]);

  const openSource = useCallback(async (documentId: string, version: number) => {
    await runTask(async () => {
      const document = await api<DocumentRecord>(`/api/documents/${encodeURIComponent(documentId)}/versions/${version}/source`);
      setModal({ kind: 'source', document });
    });
  }, [runTask]);

  const openHistory = useCallback(async (documentId: string) => {
    await runTask(async () => {
      const history = await api<DocumentRecord[]>(`/api/documents/${encodeURIComponent(documentId)}/versions`);
      setModal({ kind: 'history', documents: history });
    });
  }, [runTask]);

  const openEdit = useCallback(async (document: DocumentRecord) => {
    await runTask(async () => {
      const source = await api<DocumentRecord>(`/api/documents/${encodeURIComponent(document.id)}/versions/${document.version}/source`);
      setModal({ kind: 'edit', document: source });
    });
  }, [runTask]);

  const deleteDocument = useCallback(async (document: DocumentRecord) => {
    if (!window.confirm('Remove this document from active retrieval? Its revision history is retained.')) return;
    await runTask(async () => {
      await api(`/api/documents/${encodeURIComponent(document.id)}?expected_version=${document.version}`, { method: 'DELETE' });
      await loadDocuments();
      setNotice('Document removed from active retrieval.');
    });
  }, [loadDocuments, runTask]);

  const publishDocument = useCallback(async (form: FormData) => {
    await runTask(async () => {
      const id = String(form.get('id') || '');
      const version = String(form.get('expected_version') || '');
      const file = form.get('file') as File;
      const payload = {
        title: String(form.get('title')),
        department_id: String(form.get('department_id')),
        visibility: String(form.get('visibility')),
        evidence_type: String(form.get('evidence_type')),
        additional_evidence_types: String(form.get('additional_evidence_types') || '').split(',').map((item) => item.trim()).filter(Boolean),
        effective_at: String(form.get('effective_at')),
        expires_at: String(form.get('expires_at') || '') || null,
        content: String(form.get('content')),
        expected_version: version ? Number(version) : null,
      };
      let result: { status: string };
      if (file?.size) {
        form.delete('id');
        form.delete('content');
        if (id) form.set('document_id', id);
        if (!version) form.delete('expected_version');
        result = await api('/api/documents/upload', { method: 'POST', body: form });
      } else {
        result = await api('/api/documents' + (id ? '/' + encodeURIComponent(id) : ''), {
          method: id ? 'PUT' : 'POST',
          body: JSON.stringify(payload),
        });
      }
      await loadDocuments();
      setModal(null);
      setNotice(result.status === 'skipped' ? 'No changes: skipped re-embedding.' : 'Source published successfully.');
    });
  }, [loadDocuments, runTask]);

  const loadTrace = useCallback(async (traceId: string) => {
    await runTask(async () => {
      setTrace(await api<Trace>(`/api/traces/${encodeURIComponent(traceId)}`));
    });
  }, [runTask]);

  const runEvaluation = useCallback(async () => {
    await runTask(async () => {
      setEvaluation(await api<Evaluation>('/api/evaluate', { method: 'POST', body: JSON.stringify({ k: 5 }) }));
    });
  }, [runTask]);

  const openEvaluationTrace = useCallback(async (traceId: string) => {
    await runTask(async () => {
      setTrace(await api<Trace>(`/api/traces/${encodeURIComponent(traceId)}`));
      setTab('trace');
    });
  }, [runTask]);

  if (!session) return <LoginPage busy={busy} error={error} notice={notice} onConnect={connect} />;

  const principal = session.principal;
  const runtime = session.runtime;
  return (
    <div className="layout">
      <aside className="sidebar">
        <a className="brand" href="#" onClick={(event: MouseEvent<HTMLAnchorElement>) => { event.preventDefault(); setTab('ask'); }}>
          <span className="brandmark">R</span><span>RAGOps<span className="brand-sub">STUDIO</span></span>
        </a>
        <div className="workspace">
          <span className="avatar">{principal.tenant_id.slice(0, 1).toUpperCase()}</span>
          <div><strong>{principal.tenant_id}</strong><small>Knowledge workspace</small></div><span>⌄</span>
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          {(Object.keys(labels) as Tab[]).map((item) => (
            <button key={item} data-nav={item} className={`nav-item ${tab === item ? 'active' : ''}`} onClick={() => setTab(item)}>
              <span>{icons[item]}</span>{labels[item]}{item === 'documents' ? <small>{documents.length}</small> : null}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="runtime-status"><i /> Service connected</div>
          <div className="runtime-note">{runtime.vector_backend} index · {runtime.graph_engine} orchestration</div>
          <button className="identity" data-action="signout" onClick={signOut} disabled={busy}>
            <span className="avatar">{principal.name.slice(0, 1)}</span>
            <div><strong>{principal.name}</strong><small>{principal.department_id} · {principal.role}</small></div><span>↗</span>
          </button>
        </div>
      </aside>
      <section className="main">
        <header className="topbar">
          <div>Workspace <span>/</span> <strong>{labels[tab]}</strong></div>
          <div className="topbar-right">
            <Pill type="mode">{runtime.model_provider === 'local' ? 'Local deterministic' : runtime.chat_model}</Pill>
            <button className="button ghost small" data-action="signout" onClick={signOut} disabled={busy}>Switch identity</button>
          </div>
        </header>
        <main className="content">
          <Feedback error={error} notice={notice} />
          {tab === 'ask' ? (
            <AskWorkspace
              session={session}
              documents={documents}
              answer={answer}
              trace={trace}
              query={query}
              busy={busy}
              onQueryChange={setQuery}
              onSubmit={runQuery}
              onSampleSelect={setQuery}
              onOpenSource={openSource}
              onNavigateTrace={() => setTab('trace')}
            />
          ) : tab === 'documents' ? (
            <KnowledgeLibrary
              session={session}
              documents={documents}
              busy={busy}
              onNew={() => { setError(''); setNotice(''); setModal({ kind: 'edit', document: null }); }}
              onRefresh={() => runTask(loadDocuments)}
              onOpenSource={openSource}
              onEdit={openEdit}
              onHistory={openHistory}
              onDelete={deleteDocument}
            />
          ) : tab === 'trace' ? (
            <TraceView trace={trace} busy={busy} onLoadTrace={loadTrace} />
          ) : (
            <EvaluationView session={session} evaluation={evaluation} busy={busy} onRun={runEvaluation} onOpenTrace={openEvaluationTrace} />
          )}
        </main>
        <footer className="footer"><span>RAGOps Studio · v0.2</span><span>Tenant-scoped access · Immutable document revisions</span></footer>
      </section>
      {modal ? (
        <DocumentModal
          modal={modal}
          session={session}
          busy={busy}
          error={error}
          notice={notice}
          onClose={() => { if (!busy) { setModal(null); setError(''); } }}
          onOpenSource={openSource}
          onPublish={publishDocument}
        />
      ) : null}
    </div>
  );
}
