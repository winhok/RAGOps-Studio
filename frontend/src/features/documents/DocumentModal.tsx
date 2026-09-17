import { useEffect, type FormEvent, type MouseEvent } from 'react';
import type { DocumentRecord, Session } from '../../types';
import type { ModalState } from '../../modalTypes';
import { evidenceTypes, Feedback, formatDate, label, Pill } from '../../ui';

interface Props {
  modal: Exclude<ModalState, null>;
  session: Session;
  busy: boolean;
  error: string;
  notice: string;
  onClose: () => void;
  onOpenSource: (documentId: string, version: number) => Promise<void>;
  onPublish: (form: FormData) => Promise<void>;
}

function EditForm({ document, session, busy, onClose, onPublish }: {
  document: DocumentRecord | null;
  session: Session;
  busy: boolean;
  onClose: () => void;
  onPublish: (form: FormData) => Promise<void>;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!busy) void onPublish(new FormData(event.currentTarget));
  }

  return (
    <>
      <h2>{document ? 'Publish a new revision' : 'Add a knowledge source'}</h2>
      <p className="muted">{document ? `Current revision: v${document.version}. Unchanged content and metadata are skipped.` : 'Published sources become searchable after indexing completes.'}</p>
      <form id="document-form" onSubmit={submit}>
        <input type="hidden" name="id" value={document?.id ?? ''} />
        <input type="hidden" name="expected_version" value={document?.version ?? ''} />
        <label>Title<input name="title" required maxLength={120} defaultValue={document?.title ?? ''} /></label>
        <div className="form-grid">
          <label>Evidence type
            <select name="evidence_type" defaultValue={document?.evidence_type ?? 'general'}>
              {evidenceTypes.map((value) => <option key={value} value={value}>{label(value)}</option>)}
            </select>
          </label>
          <label>Department<input name="department_id" required pattern="([A-Za-z0-9_]|-){1,64}" defaultValue={document?.department_id ?? session.principal.department_id} /></label>
          <label>Visibility
            <select name="visibility" defaultValue={document?.visibility ?? 'company'}>
              <option value="company">company</option>
              <option value="department">department</option>
            </select>
          </label>
          <label>Effective at (ISO 8601)<input name="effective_at" required defaultValue={document?.effective_at ?? new Date().toISOString()} /></label>
        </div>
        <label>Also covers (optional evidence types)<input name="additional_evidence_types" defaultValue={document?.additional_evidence_types?.join(', ') ?? ''} placeholder="arrival_rule, material_requirement" /></label>
        <label>Expires at (optional)<input name="expires_at" defaultValue={document?.expires_at ?? ''} placeholder="2027-01-01T00:00:00+00:00" /></label>
        <label>Markdown / text content<textarea name="content" rows={7} maxLength={150000} defaultValue={document?.content ?? ''} /></label>
        <label>Or upload a source file<input type="file" name="file" accept=".md,.txt,.pdf,.docx" /></label>
        <p className="muted small-text">Markdown is the reference ingestion path. TXT, text-based PDF and DOCX are preserved from the previous release. Maximum 2 MB.</p>
        <div className="modal-actions"><button type="button" className="button ghost" onClick={onClose}>Cancel</button><button type="submit" className="button primary" disabled={busy}>{busy ? 'Publishing…' : 'Publish source'}</button></div>
      </form>
    </>
  );
}

export function DocumentModal({ modal, session, busy, error, notice, onClose, onOpenSource, onPublish }: Props) {
  useEffect(() => {
    function escape(event: KeyboardEvent) {
      if (event.key === 'Escape' && !busy) onClose();
    }
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [busy, onClose]);

  let content;
  if (modal.kind === 'edit') {
    content = <EditForm key={modal.document ? `${modal.document.id}:${modal.document.version}` : 'new'} document={modal.document} session={session} busy={busy} onClose={onClose} onPublish={onPublish} />;
  } else if (modal.kind === 'history') {
    content = (
      <>
        <h2>Revision history</h2>
        <p className="muted">Immutable source records. Only the active revision is used by retrieval.</p>
        {modal.documents.map((document) => (
          <button className="history-row" data-source={document.id} data-version={document.version} key={document.revision_id} onClick={() => void onOpenSource(document.id, document.version)}>
            <span className="revision">v{document.version}</span>
            <span><strong>{document.title}</strong><small>{formatDate(document.created_at)} · {document.chunk_count} chunks</small></span>
            <Pill type={document.active ? 'green' : 'neutral'}>{document.active ? 'Active' : 'Inactive'}</Pill>
            <span>↗</span>
          </button>
        ))}
      </>
    );
  } else {
    const document = modal.document;
    content = (
      <>
        <span className="eyebrow">STORED SOURCE · VERSION {document.version}</span>
        <h2>{document.title}</h2>
        <div className="source-metadata"><Pill>{document.visibility}</Pill><Pill>{document.department_id}</Pill><Pill type={document.active ? 'green' : 'neutral'}>{document.active ? 'Active' : 'Inactive'}</Pill></div>
        <p className="mono small-text">{document.source_path}</p>
        <pre className="source-content">{document.content}</pre>
        <div className="checksum"><span>SHA-256</span><code>{document.checksum}</code></div>
      </>
    );
  }

  return (
    <div className="modal-backdrop" onMouseDown={(event: MouseEvent<HTMLDivElement>) => { if (event.currentTarget === event.target && !busy) onClose(); }}>
      <section className="modal" role="dialog" aria-modal="true" aria-label="Knowledge source">
        <button className="modal-close" data-action="close-modal" onClick={onClose} aria-label="Close" disabled={busy}>×</button>
        <Feedback error={error} notice={notice} />
        {content}
      </section>
    </div>
  );
}
