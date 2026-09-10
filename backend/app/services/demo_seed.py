from __future__ import annotations

from pathlib import Path

from app.services.store import SQLiteDocumentStore


def seed_demo_knowledge(store: SQLiteDocumentStore, root: Path) -> int:
    knowledge = root / "data" / "knowledge"
    count = 0
    for path in sorted(knowledge.glob("*.md")):
        source_id = path.stem
        content = path.read_text(encoding="utf-8")
        title = content.splitlines()[0].removeprefix("# ").strip() or source_id
        roles = ("support", "admin") if source_id == "internal-escalation" else ("public",)
        _, duplicate = store.ingest(
            source_id=source_id,
            title=title,
            content=content,
            allowed_roles=roles,
            metadata={"source_type": "markdown", "demo": True},
        )
        if not duplicate:
            count += 1
    return count
