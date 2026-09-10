import { api, ApiError, hasCredential, setCredential } from './api.js';
const root = document.getElementById('app');
let session = null;
let tab = 'ask';
let documents = [];
let answer = null;
let trace = null;
let evaluation = null;
let query = '订单 A2026 的咖啡机退款金额是 3500 元，需要人工审核吗？准备材料时还要注意什么？';
let busy = false, error = '', notice = '', epoch = 0;
let modal = null;
const evidenceTypes = ['review_rule', 'material_requirement', 'arrival_rule', 'maintenance_policy', 'finance_policy', 'service_workflow', 'promotion_policy', 'general'];
const questions = [
    ['Multi-source', '订单 A2026 的咖啡机退款金额是 3500 元，需要人工审核吗？准备材料时还要注意什么？'],
    ['Clarification', '我的咖啡机想申请退款，需要人工审核吗？'],
    ['Policy threshold', '蓝鲸科技现在的退款金额超过多少元需要人工审核？'],
    ['Unavailable evidence', '蓝鲸科技的咖啡机是否提供终身免费上门保养？'],
    ['No retrieval', '把“请尽快处理退款”改写得更礼貌。']
];
const icons = { ask: '◈', documents: '▤', trace: '⌁', evaluation: '◫' };
const labels = { ask: 'Ask workspace', documents: 'Knowledge library', trace: 'Execution traces', evaluation: 'Evaluations' };
const escape = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const label = (value) => value.replaceAll('_', ' ');
const score = (value) => value === null ? '—' : value.toFixed(4);
const pill = (text, type = 'neutral') => `<span class="pill ${type}">${escape(text)}</span>`;
const date = (value) => new Date(value).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
const isAdmin = () => session?.principal.role === 'admin';
const message = () => `${error ? `<div role="alert" class="banner error">${escape(error)}</div>` : ''}${notice ? `<div role="status" class="banner success">${escape(notice)}</div>` : ''}`;
function render() {
    if (!session) {
        renderLogin();
        return;
    }
    const p = session.principal, r = session.runtime;
    root.innerHTML = `<div class="layout"><aside class="sidebar">
  <a class="brand" href="#"><span class="brandmark">R</span><span>RAGOps<span class="brand-sub">STUDIO</span></span></a>
  <div class="workspace"><span class="avatar">${escape(p.tenant_id.slice(0, 1).toUpperCase())}</span><div><strong>${escape(p.tenant_id)}</strong><small>Knowledge workspace</small></div><span>⌄</span></div>
  <div class="nav-label">WORKSPACE</div><nav>${['ask', 'documents', 'trace', 'evaluation'].map(t => `<button data-nav="${t}" class="nav-item ${tab === t ? 'active' : ''}"><span>${icons[t]}</span>${labels[t]}${t === 'documents' ? `<small>${documents.length}</small>` : ''}</button>`).join('')}</nav>
  <div class="sidebar-bottom"><div class="runtime-status"><i></i> Service connected</div><div class="runtime-note">${escape(r.vector_backend)} index · ${escape(r.graph_engine)} orchestration</div>
  <button class="identity" data-action="signout" ${busy ? 'disabled' : ''}><span class="avatar">${escape(p.name.slice(0, 1))}</span><div><strong>${escape(p.name)}</strong><small>${escape(p.department_id)} · ${escape(p.role)}</small></div><span>↗</span></button></div>
 </aside><section class="main"><header class="topbar"><div>Workspace <span>/</span> <strong>${labels[tab]}</strong></div><div class="topbar-right">${pill(r.model_provider === 'local' ? 'Local deterministic' : r.chat_model, 'mode')}<button class="button ghost small" data-action="signout" ${busy ? 'disabled' : ''}>Switch identity</button></div></header>
 <main class="content">${message()}${tab === 'ask' ? askView() : tab === 'documents' ? documentView() : tab === 'trace' ? traceView() : evaluationView()}</main>
 <footer class="footer"><span>RAGOps Studio · v0.2</span><span>Tenant-scoped access · Immutable document revisions</span></footer></section></div>${modal ? modalView() : ''}`;
    bind();
}
function renderLogin() {
    root.innerHTML = `<main class="login-layout"><section class="login-story"><div class="brand"><span class="brandmark">R</span><span>RAGOps Studio</span></div><div><span class="eyebrow light">KNOWLEDGE OPERATIONS</span><h1>Every answer.<br>A source you<br>can verify.</h1><p>Search with context. Respect access boundaries.<br>Know when the evidence is not enough.</p><div class="login-features"><span>01 &nbsp; Evidence-led workflows</span><span>02 &nbsp; Tenant & department access</span><span>03 &nbsp; Versioned source records</span></div></div><small>Built for inspectable knowledge workflows.</small></section>
 <section class="login-form"><div class="login-card"><span class="eyebrow">WORKSPACE ACCESS</span><h2>Connect to your workspace</h2><p>Enter a credential issued by your workspace administrator.</p>${message()}<form id="login-form"><label for="token">Access credential</label><input type="password" id="token" name="token" autocomplete="off" required placeholder="Paste your workspace credential"><button class="button primary wide" ${busy ? 'disabled' : ''}>${busy ? 'Connecting…' : 'Connect workspace →'}</button></form><div class="login-help"><strong>First time running this installation?</strong><p>Initialize workspace identities and the sample corpus:</p><code>python scripts/bootstrap.py --with-sample-data</code><p>Your generated credentials are stored locally in<br><code>.secrets/access-credentials.txt</code>.</p></div></div></section></main>`;
    document.getElementById('login-form')?.addEventListener('submit', async (e) => { e.preventDefault(); const value = document.getElementById('token').value.trim(); setCredential(value); await connect(); });
}
function askView() {
    const r = session.runtime;
    return `<div class="page-heading"><div><span class="eyebrow">AGENTIC KNOWLEDGE WORKFLOW</span><h1>Answers you can audit.</h1><p>Ask a policy question. Inspect the decision, evidence and source.</p></div><div class="heading-mark">◈</div></div>
 <div class="stat-row"><div><span>Accessible documents</span><strong>${documents.length.toString().padStart(2, '0')}</strong></div><div><span>Retrieval budget</span><strong>${r.max_searches}<small> rounds / request</small></strong></div><div><span>Retrieval pipeline</span><strong class="stat-text">Dense + BM25 <small>→ RRF → ${r.rerank_provider === 'zhipu' ? 'Model rerank' : 'Lexical rerank'}</small></strong></div></div>
 <div class="ask-grid"><section><div class="panel composer"><div class="panel-heading"><h3>Ask a question</h3>${pill('Authenticated scope', 'green')}</div><form id="query-form"><textarea id="query" maxlength="2000" rows="4" aria-label="Question">${escape(query)}</textarea><div class="composer-bottom"><span>⌕ &nbsp; ${escape(session.principal.tenant_id)} / ${escape(session.principal.department_id)}</span><button class="button primary" ${busy ? 'disabled' : ''}>${busy ? 'Searching & validating…' : 'Run query ↗'}</button></div></form></div>
 <div class="sample-queries">${questions.map(([title], i) => `<button data-question="${i}" ${busy ? 'disabled' : ''}>${escape(title)} <span>↗</span></button>`).join('')}</div>
 ${answer ? answerView() : `<div class="panel empty-answer"><span class="empty-symbol">⌁</span><h3>Your answer, with its evidence.</h3><p>The workflow can answer, ask for clarification,<br>or stop when current evidence is insufficient.</p></div>`}
 ${trace ? timeline(trace) : ''}</section><aside class="evidence-column">${evidenceView()}</aside></div>`;
}
function answerView() {
    const a = answer;
    return `<div class="panel answer-panel"><div class="panel-heading"><h3>Response</h3>${pill(a.outcome, a.outcome === 'answered' ? 'green' : a.outcome === 'refused' ? 'amber' : 'neutral')}</div><div class="answer-text">${escape(a.text)}</div><div class="answer-meta"><span>${a.search_attempts} retrieval round${a.search_attempts === 1 ? '' : 's'}</span><span>${a.timings_ms.total.toFixed(0)} ms</span><button class="text-button" data-nav="trace">Inspect trace ↗</button></div><div class="stop-reason">${escape(label(a.stop_reason))}</div></div>`;
}
function evidenceView() {
    return `<div class="panel"><div class="panel-heading"><h3>Bound sources</h3><span class="counter">${answer?.citations.length || 0}</span></div><p class="muted source-intro">Citations are resolved from stored chunks, not model-generated links.</p>${answer?.citations.length ? answer.citations.map((c, i) => `<button class="source-card" data-source="${escape(c.document_id)}" data-version="${c.version}"><div class="source-top"><span class="source-number">${i + 1}</span>${pill('v' + c.version)}</div><strong>${escape(c.title)}</strong><small>${escape(label(c.evidence_type))}</small><p>${escape(c.content.slice(0, 210))}${c.content.length > 210 ? '…' : ''}</p><span class="source-link">Open exact source ↗</span></button>`).join('') : `<div class="empty-sources"><span>▤</span><p>No citations yet.<br>Only verified evidence appears here.</p></div>`}</div>
 <div class="guard-card"><span>▣</span><div><strong>Access is checked before retrieval.</strong><p>Your tenant, department and role are resolved on the server. Replaced or deleted versions cannot enter current answers.</p></div></div>
 ${session.runtime.model_provider === 'local' ? `<div class="local-note"><strong>Local execution profile</strong><p>Rule-based routing, feature hashing and extractive answers. No external model calls. Change the server configuration to use GLM / DeepSeek and model reranking.</p></div>` : ''}`;
}
function timeline(t) { return `<div class="panel timeline"><div class="panel-heading"><h3>Execution path</h3><code>${escape(t.trace_id.slice(0, 15))}…</code></div>${t.events.map((e, i) => `<div class="timeline-step"><span>${String(i + 1).padStart(2, '0')}</span><div><strong>${escape(label(e.node))}</strong><p>${escape(e.message)}</p></div><span class="step-dot"></span></div>`).join('')}</div>`; }
function documentView() {
    return `<div class="page-heading"><div><span class="eyebrow">SOURCE GOVERNANCE</span><h1>Knowledge library</h1><p>One active revision. Clear ownership. Retrievable evidence.</p></div>${isAdmin() ? `<button class="button primary" data-action="new-document">＋ Add document</button>` : pill('Read-only access')}</div>
 <div class="panel"><div class="panel-heading"><h3>Current documents <span class="counter">${documents.length}</span></h3><button class="text-button" data-action="refresh">Refresh ↻</button></div><div class="table-wrap"><table><thead><tr><th>Document</th><th>Evidence type</th><th>Access</th><th>Revision</th><th>Status</th><th></th></tr></thead><tbody>${documents.map(d => `<tr><td><button class="document-title" data-source="${escape(d.id)}" data-version="${d.version}"><span class="file-icon">▤</span><span><strong>${escape(d.title)}</strong><small>${d.chunk_count} chunk${d.chunk_count === 1 ? '' : 's'} · ${escape(d.id)}</small></span></button></td><td>${escape(label(d.evidence_type))}</td><td>${pill(d.visibility === 'company' ? 'Company' : d.department_id)}</td><td><span class="revision">v${d.version}</span></td><td>${pill(new Date(d.effective_at) > new Date() ? 'Scheduled' : d.expires_at && new Date(d.expires_at) <= new Date() ? 'Expired' : 'Active', d.expires_at && new Date(d.expires_at) <= new Date() ? 'amber' : 'green')}</td><td class="table-actions">${isAdmin() ? `<button data-edit="${escape(d.id)}" aria-label="Edit ${escape(d.title)}">Edit</button><button data-history="${escape(d.id)}">History</button><button data-delete="${escape(d.id)}" data-version="${d.version}" class="danger">Delete</button>` : ''}</td></tr>`).join('') || '<tr><td colspan="6" class="empty-cell">No accessible documents. An administrator can add the first source.</td></tr>'}</tbody></table></div></div>
 <div class="library-notes"><div><strong>Version-safe publication</strong><p>Chunk and index preparation happen before the current revision changes. Identical content and access metadata skip re-embedding.</p></div><div><strong>Scoped by identity</strong><p>Employees see company-wide sources and their own department. Administrators stay inside their tenant boundary.</p></div></div>`;
}
function traceView() {
    return `<div class="page-heading"><div><span class="eyebrow">RETRIEVAL OBSERVABILITY</span><h1>Execution traces</h1><p>Follow every decision, search round and citation check.</p></div></div><form id="trace-form" class="trace-search"><input name="trace_id" aria-label="Trace ID" placeholder="Enter a trace ID" value="${escape(trace?.trace_id || '')}" required><button class="button secondary" ${busy ? 'disabled' : ''}>Load trace</button></form>
 ${trace ? `<div class="stat-row"><div><span>Outcome</span><strong class="stat-text">${escape(trace.outcome)}</strong></div><div><span>Search rounds</span><strong>${trace.search_attempts ?? 0}</strong></div><div><span>Total latency</span><strong>${trace.timings_ms.total.toFixed(0)}<small> ms</small></strong></div></div><p class="trace-question">${escape(trace.query)}</p>${timeline(trace)}${trace.searches.map(s => `<div class="panel round"><div class="panel-heading"><h3>Round ${s.attempt} <span class="muted">/ ${escape(label(s.evidence_type))}</span></h3>${pill(s.candidates.length + ' candidates')}</div><div class="filter-line"><span>SERVER FILTER</span><code>${escape(s.permission_filter)}</code></div><div class="round-query">${escape(s.query)}</div><div class="table-wrap"><table><thead><tr><th>Candidate</th><th>Dense</th><th>BM25</th><th>RRF</th><th>Rerank</th></tr></thead><tbody>${s.candidates.map(c => `<tr><td><strong>${escape(c.title)}</strong><small class="block mono">${escape(c.chunk_id.slice(0, 21))}… · v${c.version}</small></td><td>${score(c.dense_score)}</td><td>${score(c.lexical_score)}</td><td>${score(c.rrf_score)}</td><td><strong>${score(c.rerank_score)}</strong></td></tr>`).join('') || '<tr><td colspan="5" class="empty-cell">No candidates in this authorized scope.</td></tr>'}</tbody></table></div><div class="stage-timings">${Object.entries(s.timings_ms).map(([k, v]) => `<span>${escape(k)} <b>${v.toFixed(1)} ms</b></span>`).join('')}</div></div>`).join('')}${trace.rejected?.length ? `<div class="panel rejected"><h3>Rejected evidence</h3>${trace.rejected.map(r => `<p><code>${escape(r.chunk_id)}</code> · ${escape(label(r.reason))}</p>`).join('')}</div>` : ''}<p class="muted">A dash means the backend did not report that individual score. It is not a zero or an estimated value.</p>` : `<div class="panel empty-answer"><h3>No trace selected</h3><p>Run a question, or load an authorized trace ID.</p></div>`}`;
}
function evaluationView() {
    return `<div class="page-heading"><div><span class="eyebrow">QUALITY REGRESSION</span><h1>Evaluate the retrieval path.</h1><p>Repeatable checks against a small, synthetic policy corpus.</p></div>${isAdmin() ? `<button class="button primary" data-action="evaluate" ${busy ? 'disabled' : ''}>${busy ? 'Running…' : 'Run regression ↗'}</button>` : pill('Administrator access required')}</div><div class="banner neutral">These results measure the bundled synthetic cases. They are not production accuracy or an answer-faithfulness score.</div>
 ${evaluation ? `<div class="stat-row eval-stats">${[['Recall@' + evaluation.k, evaluation.summary.recall_at_k], ['MRR', evaluation.summary.mrr], ['nDCG@' + evaluation.k, evaluation.summary.ndcg_at_k], ['Keyword coverage', evaluation.summary.keyword_coverage]].map(([name, value]) => `<div><span>${name}</span><strong>${(Number(value) * 100).toFixed(1)}<small>%</small></strong></div>`).join('')}</div><div class="panel"><div class="panel-heading"><h3>${evaluation.summary.cases} evaluated questions</h3>${pill(evaluation.runtime.model_provider)}</div><div class="table-wrap"><table><thead><tr><th>Question</th><th>Outcome</th><th>Recall</th><th>MRR</th><th></th></tr></thead><tbody>${evaluation.cases.map(c => `<tr><td class="eval-question">${escape(c.query)}</td><td>${pill(c.outcome, c.outcome === 'answered' ? 'green' : 'neutral')}</td><td>${c.recall_at_k.toFixed(2)}</td><td>${c.reciprocal_rank.toFixed(2)}</td><td><button class="text-button" data-trace="${escape(c.trace_id)}">Trace ↗</button></td></tr>`).join('')}</tbody></table></div></div><p class="muted">${escape(evaluation.metric_scope)}</p>` : `<div class="panel empty-answer"><span class="empty-symbol">◫</span><h3>A baseline, not a vanity metric.</h3><p>Run the existing evaluation suite to inspect document-level<br>Recall@K, MRR, nDCG@K and keyword coverage.</p></div>`}`;
}
function modalView() {
    if (!modal)
        return '';
    let inner = '';
    if (modal.kind === 'edit') {
        const d = modal.document;
        const opts = (values, selected) => values.map(v => `<option value="${escape(v)}" ${selected === v ? 'selected' : ''}>${escape(label(v))}</option>`).join('');
        inner = `<h2>${d ? 'Publish a new revision' : 'Add a knowledge source'}</h2><p class="muted">${d ? `Current revision: v${d.version}. Unchanged content and metadata are skipped.` : 'Published sources become searchable after indexing completes.'}</p><form id="document-form"><input type="hidden" name="id" value="${escape(d?.id || '')}"><input type="hidden" name="expected_version" value="${d?.version || ''}"><label>Title<input name="title" required maxlength="120" value="${escape(d?.title || '')}"></label><div class="form-grid"><label>Evidence type<select name="evidence_type">${opts(evidenceTypes, d?.evidence_type || 'general')}</select></label><label>Department<input name="department_id" required pattern="([A-Za-z0-9_]|-){1,64}" value="${escape(d?.department_id || session.principal.department_id)}"></label><label>Visibility<select name="visibility">${opts(['company', 'department'], d?.visibility || 'company')}</select></label><label>Effective at (ISO 8601)<input name="effective_at" required value="${escape(d?.effective_at || new Date().toISOString())}"></label></div><label>Also covers (optional evidence types)<input name="additional_evidence_types" value="${escape(d?.additional_evidence_types?.join(', ') || '')}" placeholder="arrival_rule, material_requirement"></label><label>Expires at (optional)<input name="expires_at" value="${escape(d?.expires_at || '')}" placeholder="2027-01-01T00:00:00+00:00"></label><label>Markdown / text content<textarea name="content" rows="7" maxlength="150000">${escape(d?.content || '')}</textarea></label><label>Or upload a source file<input type="file" name="file" accept=".md,.txt,.pdf,.docx"></label><p class="muted small-text">Markdown is the reference ingestion path. TXT, text-based PDF and DOCX are preserved from the previous release. Maximum 2 MB.</p><div class="modal-actions"><button type="button" class="button ghost" data-action="close-modal">Cancel</button><button class="button primary" ${busy ? 'disabled' : ''}>${busy ? 'Publishing…' : 'Publish source'}</button></div></form>`;
    }
    else if (modal.kind === 'history') {
        inner = `<h2>Revision history</h2><p class="muted">Immutable source records. Only the active revision is used by retrieval.</p>${modal.documents.map(d => `<button class="history-row" data-source="${escape(d.id)}" data-version="${d.version}"><span class="revision">v${d.version}</span><span><strong>${escape(d.title)}</strong><small>${date(d.created_at)} · ${d.chunk_count} chunks</small></span>${pill(d.active ? 'Active' : 'Inactive', d.active ? 'green' : 'neutral')}<span>↗</span></button>`).join('')}`;
    }
    else {
        const d = modal.document;
        inner = `<span class="eyebrow">STORED SOURCE · VERSION ${d.version}</span><h2>${escape(d.title)}</h2><div class="source-metadata">${pill(d.visibility)}${pill(d.department_id)}${pill(d.active ? 'Active' : 'Inactive', d.active ? 'green' : 'neutral')}</div><p class="mono small-text">${escape(d.source_path)}</p><pre class="source-content">${escape(d.content)}</pre><div class="checksum"><span>SHA-256</span><code>${escape(d.checksum)}</code></div>`;
    }
    return `<div class="modal-backdrop"><section class="modal" role="dialog" aria-modal="true" aria-label="Knowledge source"><button class="modal-close" data-action="close-modal" aria-label="Close">×</button>${message()}${inner}</section></div>`;
}
function bind() {
    root.querySelectorAll('[data-nav]').forEach(el => el.addEventListener('click', () => { tab = el.dataset.nav; render(); }));
    root.querySelectorAll('[data-question]').forEach(el => el.addEventListener('click', () => { query = questions[Number(el.dataset.question)][1]; render(); }));
    root.querySelectorAll('[data-action]').forEach(el => el.addEventListener('click', () => {
        switch (el.dataset.action) {
            case 'signout':
                if (busy)
                    return;
                epoch++;
                tab = 'ask';
                query = questions[0][1];
                setCredential('');
                session = null;
                documents = [];
                answer = null;
                trace = null;
                evaluation = null;
                modal = null;
                busy = false;
                error = '';
                notice = '';
                render();
                break;
            case 'refresh':
                void task(async () => { documents = await api('/api/documents'); });
                break;
            case 'new-document':
                modal = { kind: 'edit', document: null };
                error = '';
                notice = '';
                render();
                break;
            case 'close-modal':
                modal = null;
                error = '';
                render();
                break;
            case 'evaluate':
                void task(async () => { evaluation = await api('/api/evaluate', { method: 'POST', body: JSON.stringify({ k: 5 }) }); });
                break;
        }
    }));
    root.querySelectorAll('[data-source]').forEach(el => el.addEventListener('click', () => void task(async () => { const doc = await api(`/api/documents/${encodeURIComponent(el.dataset.source)}/versions/${el.dataset.version}/source`); modal = { kind: 'source', document: doc }; })));
    root.querySelectorAll('[data-history]').forEach(el => el.addEventListener('click', () => void task(async () => { modal = { kind: 'history', documents: await api(`/api/documents/${encodeURIComponent(el.dataset.history)}/versions`) }; })));
    root.querySelectorAll('[data-edit]').forEach(el => el.addEventListener('click', () => void task(async () => { const doc = documents.find(d => d.id === el.dataset.edit); modal = { kind: 'edit', document: await api(`/api/documents/${encodeURIComponent(doc.id)}/versions/${doc.version}/source`) }; })));
    root.querySelectorAll('[data-delete]').forEach(el => el.addEventListener('click', () => {
        if (!confirm('Remove this document from active retrieval? Its revision history is retained.'))
            return;
        void task(async () => { await api(`/api/documents/${encodeURIComponent(el.dataset.delete)}?expected_version=${el.dataset.version}`, { method: 'DELETE' }); documents = await api('/api/documents'); notice = 'Document removed from active retrieval.'; });
    }));
    root.querySelectorAll('[data-trace]').forEach(el => el.addEventListener('click', () => void task(async () => { trace = await api('/api/traces/' + encodeURIComponent(el.dataset.trace)); tab = 'trace'; })));
    document.getElementById('query-form')?.addEventListener('submit', e => {
        e.preventDefault();
        query = document.getElementById('query').value.trim();
        if (!query)
            return;
        if (busy)
            return;
        answer = null;
        trace = null;
        void task(async () => { answer = await api('/api/chat', { method: 'POST', body: JSON.stringify({ query, top_k: 4 }) }); trace = await api('/api/traces/' + answer.trace_id); });
    });
    document.getElementById('query')?.addEventListener('input', e => { query = e.target.value; });
    document.getElementById('trace-form')?.addEventListener('submit', e => { e.preventDefault(); const id = String(new FormData(e.target).get('trace_id')).trim(); void task(async () => { trace = await api('/api/traces/' + encodeURIComponent(id)); }); });
    document.getElementById('document-form')?.addEventListener('submit', e => {
        e.preventDefault();
        const form = new FormData(e.target);
        void task(async () => {
            const id = String(form.get('id') || ''), version = String(form.get('expected_version') || ''), file = form.get('file');
            const payload = { title: String(form.get('title')), department_id: String(form.get('department_id')), visibility: String(form.get('visibility')), evidence_type: String(form.get('evidence_type')), additional_evidence_types: String(form.get('additional_evidence_types') || '').split(',').map(x => x.trim()).filter(Boolean), effective_at: String(form.get('effective_at')), expires_at: String(form.get('expires_at') || '') || null, content: String(form.get('content')), expected_version: version ? Number(version) : null };
            let result;
            if (file?.size) {
                form.delete('id');
                form.delete('content');
                if (id)
                    form.set('document_id', id);
                if (!version)
                    form.delete('expected_version');
                result = await api('/api/documents/upload', { method: 'POST', body: form });
            }
            else {
                result = await api('/api/documents' + (id ? '/' + encodeURIComponent(id) : ''), { method: id ? 'PUT' : 'POST', body: JSON.stringify(payload) });
            }
            documents = await api('/api/documents');
            modal = null;
            notice = result.status === 'skipped' ? 'No changes: skipped re-embedding.' : 'Source published successfully.';
        });
    });
}
async function task(work) {
    if (busy)
        return;
    busy = true;
    error = '';
    notice = '';
    const current = epoch;
    render();
    try {
        await work();
    }
    catch (e) {
        if (current !== epoch)
            return;
        error = e instanceof Error ? e.message : 'Request failed';
        if (e instanceof ApiError && e.traceId)
            error += ' · Trace ' + e.traceId;
    }
    finally {
        if (current === epoch) {
            busy = false;
            render();
        }
    }
}
async function connect() {
    busy = true;
    error = '';
    render();
    try {
        session = await api('/api/session');
        documents = await api('/api/documents');
    }
    catch (e) {
        setCredential('');
        session = null;
        error = e instanceof Error ? e.message : 'Unable to connect';
    }
    finally {
        busy = false;
        render();
    }
}
document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && modal && !busy) {
        modal = null;
        render();
    }
});
if (hasCredential())
    void connect();
else
    render();
