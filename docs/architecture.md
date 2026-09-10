# Architecture notes

## Retrieval path

1. Resolve the current active version of each logical document.
2. Filter chunks by caller role before any ranking step.
3. Rank the same candidate set independently with BM25 and dense similarity.
4. Fuse rankings with Reciprocal Rank Fusion (RRF).
5. Rerank the fused candidate set.
6. Generate a grounded answer from retrieved evidence.
7. Return explicit citations and persist a trace containing component scores and latency.

The core algorithms are framework-agnostic so they are deterministic and unit-testable. `services/graph.py` provides the LangGraph composition layer used by the API.

## Persistence boundaries

SQLite is the source of truth for document content, versions, access metadata, and traces. Dense retrieval can run in memory for tests or use Qdrant via `RAGOPS_VECTOR_BACKEND=qdrant`.

In the Qdrant profile, the current active/authorized chunk list remains authoritative. Qdrant results are intersected with that set before fusion, preventing stale vectors from reviving inactive versions.

## Provider boundaries

The system has two useful profiles:

- **offline**: deterministic hashed embeddings + extractive grounded answerer. Useful for tests, demos, and CI.
- **provider**: OpenAI-compatible embeddings + LLM answer generation; Qdrant can be enabled independently.

This separation keeps tests stable while preserving a realistic integration path.

## Security model

The current portfolio demonstrates retrieval-time role filtering. A production service should authenticate the caller, resolve tenant/role claims server-side, scope storage by tenant, encrypt sensitive data, audit privileged queries, and enforce tool permissions independently of the LLM.
