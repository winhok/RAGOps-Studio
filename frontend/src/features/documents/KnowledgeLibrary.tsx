import type { DocumentRecord, Session } from '../../types';
import { label, Pill } from '../../ui';

interface Props {
  session: Session;
  documents: DocumentRecord[];
  busy: boolean;
  onNew: () => void;
  onRefresh: () => Promise<void>;
  onOpenSource: (documentId: string, version: number) => Promise<void>;
  onEdit: (document: DocumentRecord) => Promise<void>;
  onHistory: (documentId: string) => Promise<void>;
  onDelete: (document: DocumentRecord) => Promise<void>;
}

function statusFor(document: DocumentRecord) {
  if (new Date(document.effective_at) > new Date()) return { text: 'Scheduled', type: 'neutral' };
  if (document.expires_at && new Date(document.expires_at) <= new Date()) return { text: 'Expired', type: 'amber' };
  return { text: 'Active', type: 'green' };
}

export function KnowledgeLibrary({ session, documents, busy, onNew, onRefresh, onOpenSource, onEdit, onHistory, onDelete }: Props) {
  const isAdmin = session.principal.role === 'admin';

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">SOURCE GOVERNANCE</span>
          <h1>Knowledge library</h1>
          <p>One active revision. Clear ownership. Retrievable evidence.</p>
        </div>
        {isAdmin ? <button className="button primary" data-action="new-document" onClick={onNew}>＋ Add document</button> : <Pill>Read-only access</Pill>}
      </div>
      <div className="panel">
        <div className="panel-heading">
          <h3>Current documents <span className="counter">{documents.length}</span></h3>
          <button className="text-button" data-action="refresh" onClick={() => void onRefresh()} disabled={busy}>Refresh ↻</button>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Document</th><th>Evidence type</th><th>Access</th><th>Revision</th><th>Status</th><th /></tr></thead>
            <tbody>
              {documents.length ? documents.map((document) => {
                const status = statusFor(document);
                return (
                  <tr key={`${document.id}-${document.version}`}>
                    <td>
                      <button className="document-title" data-source={document.id} data-version={document.version} onClick={() => void onOpenSource(document.id, document.version)}>
                        <span className="file-icon">▤</span>
                        <span><strong>{document.title}</strong><small>{document.chunk_count} chunk{document.chunk_count === 1 ? '' : 's'} · {document.id}</small></span>
                      </button>
                    </td>
                    <td>{label(document.evidence_type)}</td>
                    <td><Pill>{document.visibility === 'company' ? 'Company' : document.department_id}</Pill></td>
                    <td><span className="revision">v{document.version}</span></td>
                    <td><Pill type={status.type}>{status.text}</Pill></td>
                    <td className="table-actions">
                      {isAdmin ? (
                        <>
                          <button data-edit={document.id} onClick={() => void onEdit(document)} aria-label={`Edit ${document.title}`}>Edit</button>
                          <button data-history={document.id} onClick={() => void onHistory(document.id)}>History</button>
                          <button className="danger" data-delete={document.id} data-version={document.version} onClick={() => void onDelete(document)}>Delete</button>
                        </>
                      ) : null}
                    </td>
                  </tr>
                );
              }) : <tr><td colSpan={6} className="empty-cell">No accessible documents. An administrator can add the first source.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      <div className="library-notes">
        <div><strong>Version-safe publication</strong><p>Chunk and index preparation happen before the current revision changes. Identical content and access metadata skip re-embedding.</p></div>
        <div><strong>Scoped by identity</strong><p>Employees see company-wide sources and their own department. Administrators stay inside their tenant boundary.</p></div>
      </div>
    </>
  );
}
