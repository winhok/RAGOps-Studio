# Changelog

## Unreleased — Structured sources and relevance inspection

- Preserve Word heading levels, list items, table cells and body order during source import.
- Repeat table headers across bounded chunks and reject oversized rows before source activation.
- Assess supporting chunks before generation and permit one distinct query revision within the existing search budget.
- Show per-round relevance outcomes and revised queries in the trace console.
- Add a synthetic Word demonstration generator and regression/provider-contract checks without adding runtime services.

## Unreleased — React operations console

- Restored the frontend as a React 19 + TypeScript + Vite application while preserving the existing RAGOps workflows and UI behavior.
- Split the console into feature-level views for authentication, agentic Q&A, source governance, retrieval traces and evaluation.
- Added a Vite development proxy and a production build that is served by FastAPI from `frontend/dist`.
- Changed the Docker image to a multi-stage build so frontend dependencies and source files are not shipped in the Python runtime image.
- Stopped versioning generated frontend build artifacts; CI now builds the console from source.
- Updated React/Vite dependencies to maintained releases and added a CI gate for high-severity npm advisories.

## 0.2.0 — Governed knowledge workflows

- Connected evidence-seeking decisions and bounded follow-up retrieval to the persisted knowledge base.
- Added server-issued tenant/department identities, authenticated APIs, administrator document maintenance and source revalidation.
- Added Markdown heading paths, active-revision change detection, immutable sources, expected-version updates and soft deletion.
- Added native Milvus hybrid and Zhipu/DeepSeek adapters; retained explicit local and existing compatibility backends.
- Added behavior/security/provider-contract tests and explicit opt-in live integration checks.
- Organized evidence-seeking and source-maintenance demonstration data into separate tenant namespaces and made sample-data ingestion explicit.

There is no automatic migration from a v0.1 database. Keep the old package intact and use a new state directory. No previous private data is bundled in this release.
