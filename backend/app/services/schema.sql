PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS revisions (
    revision_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, tenant_id TEXT NOT NULL,
    version INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 0,
    payload TEXT NOT NULL, UNIQUE(tenant_id, document_id, version));
CREATE UNIQUE INDEX IF NOT EXISTS current_revision ON revisions(tenant_id, document_id) WHERE active=1;
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY, revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
    tenant_id TEXT NOT NULL, department_id TEXT NOT NULL, visibility TEXT NOT NULL,
    evidence_type TEXT NOT NULL, payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS chunk_scope ON chunks(tenant_id, evidence_type, revision_id);
CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, user_id TEXT NOT NULL,
    created_at TEXT NOT NULL, payload TEXT NOT NULL);
PRAGMA user_version=2;
