from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from pathlib import Path

from app.core.chunking import chunk_document
from app.core.models import Chunk, Document


class SQLiteDocumentStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    checksum TEXT NOT NULL,
                    allowed_roles TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_source_version
                    ON documents(source_id, version);
                CREATE INDEX IF NOT EXISTS idx_documents_active
                    ON documents(source_id, active);
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def ingest(
        self,
        *,
        source_id: str,
        title: str,
        content: str,
        allowed_roles: tuple[str, ...] = ("public",),
        metadata: dict | None = None,
    ) -> tuple[Document, bool]:
        normalized = content.strip()
        checksum = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        metadata = metadata or {}

        with self._lock, self._connect() as conn:
            duplicate = conn.execute(
                "SELECT * FROM documents WHERE source_id = ? AND checksum = ? ORDER BY version DESC LIMIT 1",
                (source_id, checksum),
            ).fetchone()
            if duplicate:
                return self._row_to_document(duplicate), True

            row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS max_version FROM documents WHERE source_id = ?",
                (source_id,),
            ).fetchone()
            version = int(row["max_version"]) + 1
            conn.execute("UPDATE documents SET active = 0 WHERE source_id = ?", (source_id,))
            document = Document(
                id=f"doc_{uuid.uuid4().hex[:12]}",
                source_id=source_id,
                title=title,
                content=normalized,
                version=version,
                checksum=checksum,
                allowed_roles=tuple(dict.fromkeys(allowed_roles)) or ("public",),
                metadata=metadata,
                active=True,
            )
            conn.execute(
                """
                INSERT INTO documents(id, source_id, title, content, version, checksum, allowed_roles, metadata, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    document.id,
                    document.source_id,
                    document.title,
                    document.content,
                    document.version,
                    document.checksum,
                    json.dumps(document.allowed_roles),
                    json.dumps(document.metadata),
                ),
            )
            conn.commit()
            return document, False

    def list_documents(self, *, include_inactive: bool = False) -> list[Document]:
        sql = "SELECT * FROM documents"
        if not include_inactive:
            sql += " WHERE active = 1"
        sql += " ORDER BY source_id, version DESC"
        with self._connect() as conn:
            return [self._row_to_document(row) for row in conn.execute(sql).fetchall()]

    def active_chunks(self, *, role: str) -> list[Chunk]:
        documents = self.list_documents(include_inactive=False)
        chunks: list[Chunk] = []
        for document in documents:
            if not self._role_allowed(role, document.allowed_roles):
                continue
            chunks.extend(chunk_document(document))
        return chunks

    @staticmethod
    def _role_allowed(role: str, allowed_roles: tuple[str, ...]) -> bool:
        return "public" in allowed_roles or role in allowed_roles or "*" in allowed_roles

    def save_trace(self, trace_id: str, payload: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO traces(trace_id, payload) VALUES (?, ?)",
                (trace_id, json.dumps(payload, ensure_ascii=False)),
            )
            conn.commit()

    def get_trace(self, trace_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM traces WHERE trace_id = ?", (trace_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    @staticmethod
    def _row_to_document(row: sqlite3.Row) -> Document:
        return Document(
            id=row["id"],
            source_id=row["source_id"],
            title=row["title"],
            content=row["content"],
            version=int(row["version"]),
            checksum=row["checksum"],
            allowed_roles=tuple(json.loads(row["allowed_roles"])),
            metadata=json.loads(row["metadata"]),
            active=bool(row["active"]),
        )
