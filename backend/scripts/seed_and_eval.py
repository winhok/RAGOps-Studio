from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.models import BenchmarkCase
from app.services.evaluation import Evaluator
from app.services.pipeline import RAGPipeline
from app.services.store import SQLiteDocumentStore


def seed(store: SQLiteDocumentStore) -> None:
    knowledge = ROOT / "data" / "knowledge"
    for path in sorted(knowledge.glob("*.md")):
        source_id = path.stem
        roles = ("support", "admin") if source_id == "internal-escalation" else ("public",)
        store.ingest(
            source_id=source_id,
            title=path.read_text(encoding="utf-8").splitlines()[0].removeprefix("# "),
            content=path.read_text(encoding="utf-8"),
            allowed_roles=roles,
            metadata={"source_type": "markdown", "demo": True},
        )


def load_cases() -> list[BenchmarkCase]:
    rows = json.loads((ROOT / "data" / "benchmark.json").read_text(encoding="utf-8"))
    return [
        BenchmarkCase(
            query=row["query"],
            relevant_source_ids=tuple(row["relevant_source_ids"]),
            expected_keywords=tuple(row.get("expected_keywords", [])),
            role=row.get("role", "public"),
        )
        for row in rows
    ]


def main() -> None:
    db_path = ROOT / "data" / "ragops-demo.db"
    if db_path.exists():
        db_path.unlink()
    store = SQLiteDocumentStore(db_path)
    seed(store)
    result = Evaluator(RAGPipeline(store)).evaluate(load_cases(), k=5)
    output = ROOT / "data" / "benchmark-results.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print(f"Saved detailed results to {output}")


if __name__ == "__main__":
    main()
