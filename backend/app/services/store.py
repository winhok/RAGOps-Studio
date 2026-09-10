from __future__ import annotations
import hashlib
import json
import os
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Iterator
from app.api.schemas import SaveDocumentRequest
from app.core.auth import can_read
from app.core.chunking import chunk_document, normalize_markdown
from app.core.errors import AppError, Conflict, Forbidden, NotFound
from app.core.models import Chunk, Document, Principal, iso_now, utcnow

class SQLiteDocumentStore:
    """Revision metadata is authoritative; vector indexes hold immutable chunk revisions."""

    def __init__(self, path: Path | str, *, max_active_chunks: int=5000):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.source_root = self.path.parent / 'sources'
        self.max_active_chunks = max_active_chunks
        self._writer = threading.RLock()
        with self.connection() as conn:
            old = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='documents'").fetchone()
            if old:
                raise Conflict('Legacy database detected. Use a new RAGOPS_STATE_DIR; existing data was not modified.')
            conn.executescript(Path(__file__).with_name('schema.sql').read_text(encoding='utf-8'))

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def bind_index_configuration(self, fingerprint: dict):
        value = json.dumps(fingerprint, sort_keys=True)
        with self.connection() as conn:
            old = conn.execute("SELECT value FROM settings WHERE key='index_configuration'").fetchone()
            if old and old['value'] != value:
                raise Conflict('Embedding/index configuration changed. Use a new state directory and collection, then re-ingest sources.')
            conn.execute("INSERT OR IGNORE INTO settings VALUES ('index_configuration', ?)", (value,))

    @staticmethod
    def _document(row) -> Document:
        payload = json.loads(row['payload'])
        payload['active'] = bool(row['active'])
        return Document(**payload)

    def versions(self, principal: Principal, document_id: str) -> list[Document]:
        if principal.role != 'admin':
            raise Forbidden('Version history is restricted to tenant administrators')
        with self.connection() as conn:
            rows = conn.execute('SELECT * FROM revisions WHERE tenant_id=? AND document_id=? ORDER BY version DESC', (principal.tenant_id, document_id)).fetchall()
        if not rows:
            raise NotFound('Document not found')
        return [self._document(row) for row in rows]

    def list_documents(self, principal: Principal) -> list[Document]:
        with self.connection() as conn:
            rows = conn.execute('SELECT * FROM revisions WHERE tenant_id=? AND active=1 ORDER BY document_id', (principal.tenant_id,)).fetchall()
        docs = [self._document(row) for row in rows]
        return [d for d in docs if can_read(principal, d.tenant_id, d.department_id, d.visibility)]

    def source(self, principal: Principal, document_id: str, version: int) -> Document:
        with self.connection() as conn:
            row = conn.execute('SELECT * FROM revisions WHERE tenant_id=? AND document_id=? AND version=?', (principal.tenant_id, document_id, version)).fetchone()
        if not row:
            raise NotFound('Source not found')
        doc = self._document(row)
        if not can_read(principal, doc.tenant_id, doc.department_id, doc.visibility):
            raise NotFound('Source not found')
        if principal.role != 'admin' and (not doc.active or not valid_dates(doc.effective_at, doc.expires_at, utcnow())):
            raise NotFound('Source version is no longer available')
        return doc

    def publish(self, principal: Principal, data: SaveDocumentRequest, embedding, index, document_id: str | None=None, *, must_exist: bool=False) -> dict:
        if principal.role != 'admin':
            raise Forbidden('Administrator role required')
        document_id = document_id or f'doc_{uuid.uuid4().hex[:16]}'
        for value in (principal.tenant_id, document_id):
            if not re.fullmatch('[A-Za-z0-9_-]{1,96}', value):
                raise AppError('Invalid document or tenant identifier')
        content = normalize_markdown(data.content)
        if not content:
            raise AppError('Document contains no usable text')
        checksum = hashlib.sha256(content.encode()).hexdigest()
        identity = (checksum, data.title, data.department_id, data.visibility, data.evidence_type, data.effective_at.isoformat(), data.expires_at.isoformat() if data.expires_at else None, tuple(data.additional_evidence_types))
        with self._writer:
            with self.connection() as conn:
                rows = conn.execute('SELECT * FROM revisions WHERE tenant_id=? AND document_id=? ORDER BY version DESC', (principal.tenant_id, document_id)).fetchall()
                active = next((self._document(row) for row in rows if row['active']), None)
                version = (int(rows[0]['version']) if rows else 0) + 1
            if must_exist and active is None:
                raise NotFound('Active document not found')
            actual_version = active.version if active else 0
            if data.expected_version is not None and data.expected_version != actual_version:
                raise Conflict(f'Expected version {data.expected_version}; active version is {actual_version}. Reload before updating.')
            if active:
                previous = (active.checksum, active.title, active.department_id, active.visibility, active.evidence_type, active.effective_at, active.expires_at, tuple(active.additional_evidence_types))
                if identity == previous:
                    return {'status': 'skipped', 'document': document_summary(active), 'duplicate': True}
            doc = Document(id=document_id, revision_id=f'rev_{uuid.uuid4().hex}', tenant_id=principal.tenant_id, title=data.title, content=content, version=version, checksum=checksum, department_id=data.department_id, visibility=data.visibility, evidence_type=data.evidence_type, effective_at=data.effective_at.isoformat(), expires_at=data.expires_at.isoformat() if data.expires_at else None, source_path=f'{principal.tenant_id}/{document_id}/v{version}.md', additional_evidence_types=data.additional_evidence_types)
            chunks = chunk_document(doc)
            if not chunks:
                raise AppError('Document contains headings but no indexable body')
            if len(chunks) > 400:
                raise AppError('Document exceeds the 400 chunk limit')
            with self.connection() as conn:
                active_count = conn.execute('SELECT count(*) FROM chunks c JOIN revisions r ON c.revision_id=r.revision_id WHERE r.tenant_id=? AND r.active=1 AND r.document_id != ?', (principal.tenant_id, document_id)).fetchone()[0]
            if active_count + len(chunks) > self.max_active_chunks:
                raise AppError('Workspace chunk limit reached; reduce content before publication')
            vectors = embedding.embed_many([chunk.text for chunk in chunks])
            if len(vectors) != len(chunks):
                raise AppError('Embedding count does not match chunk count')
            for chunk, vector in zip(chunks, vectors, strict=True):
                chunk.vector = vector
            doc.chunk_count = len(chunks)
            # Index immutable new IDs first. Until the SQL transaction commits, no reader can request them.
            index.stage(chunks)
            source = self.source_root / doc.source_path
            source.parent.mkdir(parents=True, exist_ok=True)
            temp = source.with_suffix(f'.{uuid.uuid4().hex}.tmp')
            try:
                with temp.open('w', encoding='utf-8') as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                with self.connection() as conn:
                    conn.execute('BEGIN IMMEDIATE')
                    latest = conn.execute('SELECT COALESCE(MAX(version),0) FROM revisions WHERE tenant_id=? AND document_id=?', (principal.tenant_id, document_id)).fetchone()[0]
                    if latest != version - 1:
                        raise Conflict('A concurrent writer published this document. Reload and retry.')
                    current = conn.execute('SELECT version FROM revisions WHERE tenant_id=? AND document_id=? AND active=1', (principal.tenant_id, document_id)).fetchone()
                    if (int(current[0]) if current else 0) != actual_version:
                        raise Conflict('The active document changed during publication')
                    os.replace(temp, source)
                    conn.execute('UPDATE revisions SET active=0 WHERE tenant_id=? AND document_id=?', (principal.tenant_id, document_id))
                    conn.execute('INSERT INTO revisions VALUES (?,?,?,?,1,?)', (doc.revision_id, document_id, principal.tenant_id, version, json.dumps(asdict(doc), ensure_ascii=False)))
                    for chunk in chunks:
                        conn.execute('INSERT INTO chunks VALUES (?,?,?,?,?,?,?)', (chunk.id, doc.revision_id, principal.tenant_id, doc.department_id, doc.visibility, doc.evidence_type, json.dumps(asdict(chunk), ensure_ascii=False)))
            finally:
                temp.unlink(missing_ok=True)
            return {'status': 'updated' if rows else 'created', 'document': document_summary(doc), 'duplicate': False}

    def delete(self, principal: Principal, document_id: str, expected_version: int) -> dict:
        if principal.role != 'admin':
            raise Forbidden('Administrator role required')
        with self._writer, self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            rows = conn.execute('SELECT * FROM revisions WHERE tenant_id=? AND document_id=? ORDER BY version DESC', (principal.tenant_id, document_id)).fetchall()
            if not rows:
                raise NotFound('Document not found')
            active = next((row for row in rows if row['active']), None)
            if not active:
                return {'status': 'skipped'}
            if active['version'] != expected_version:
                raise Conflict('Document version changed; reload before deleting')
            conn.execute('UPDATE revisions SET active=0 WHERE tenant_id=? AND document_id=?', (principal.tenant_id, document_id))
        return {'status': 'deleted'}

    def snapshot(self, principal: Principal, evidence_type: str | None=None) -> list[Chunk]:
        # The same authorized snapshot constrains local BM25, dense search, and both external ANN requests.
        sql = 'SELECT c.payload FROM chunks c JOIN revisions r ON c.revision_id=r.revision_id WHERE r.active=1 AND c.tenant_id=?'
        params: list = [principal.tenant_id]
        if principal.role != 'admin':
            sql += " AND (c.visibility='company' OR c.department_id=?)"
            params.append(principal.department_id)
        if evidence_type and evidence_type != 'general':
            sql += " AND (c.evidence_type=? OR EXISTS (SELECT 1 FROM json_each(c.payload, '$.additional_evidence_types') WHERE value=?))"
            params.extend([evidence_type, evidence_type])
        sql += ' ORDER BY c.chunk_id LIMIT ?'
        params.append(self.max_active_chunks + 1)
        with self.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        if len(rows) > self.max_active_chunks:
            raise AppError('Authorized snapshot exceeds configured limit')
        return [Chunk(**json.loads(row['payload'])) for row in rows]

    def current_ids(self, principal: Principal) -> set[str]:
        now = utcnow()
        return {c.id for c in self.snapshot(principal) if valid_dates(c.effective_at, c.expires_at, now)}

    def save_trace(self, principal: Principal, trace_id: str, payload: dict):
        with self.connection() as conn:
            conn.execute('INSERT OR REPLACE INTO traces VALUES (?,?,?,?,?)', (trace_id, principal.tenant_id, principal.user_id, iso_now(), json.dumps(payload, ensure_ascii=False)))

    def get_trace(self, principal: Principal, trace_id: str) -> dict:
        with self.connection() as conn:
            row = conn.execute('SELECT * FROM traces WHERE trace_id=? AND tenant_id=?', (trace_id, principal.tenant_id)).fetchone()
        if not row or (principal.role != 'admin' and row['user_id'] != principal.user_id):
            raise NotFound('Trace not found')
        payload = json.loads(row['payload'])
        # Revoked or superseded source bodies must not remain readable through an old trace URL.
        active = self.current_ids(principal)
        if principal.role != 'admin':
            for step in payload.get('searches', []):
                step['candidates'] = [r for r in step['candidates'] if r['chunk_id'] in active]
            payload['citations'] = [c for c in payload.get('citations', []) if c['chunk_id'] in active]
            if any((c not in active for c in payload.get('cited_ids', []))):
                payload['answer'] = '[Source access changed; run the question again.]'
        return payload

def valid_dates(effective_at: str, expires_at: str | None, now: datetime) -> bool:
    try:
        effective = datetime.fromisoformat(effective_at)
        expires = datetime.fromisoformat(expires_at) if expires_at else None
        if effective.tzinfo is None or (expires and expires.tzinfo is None):
            return False
        return effective <= now and (expires is None or expires > now)
    except (TypeError, ValueError):
        return False

def document_summary(document: Document) -> dict:
    return {k: v for k, v in asdict(document).items() if k != 'content'}
