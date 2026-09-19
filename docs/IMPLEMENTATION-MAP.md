# Implementation and verification map

This map connects the application's capabilities to their implementation and checks. For recorded results and unverified integrations, see [VALIDATION.md](VALIDATION.md).

## Evidence-seeking workflow

| Capability | Implementation | Verification |
|---|---|---|
| Direct, clarify and retrieve routes | `backend/app/services/graph.py`, `backend/app/core/models.py` | Route selection, missing user input and zero-retrieval responses |
| Bounded retrieval | Shared Python/LangGraph workflow nodes and `RetrievalTool` | Missing-type search order, search budget and stop conditions |
| Relevance assessment and one query revision | `backend/app/services/providers.py`, `backend/app/services/graph.py` | Irrelevant candidates, distinct-query retry, repeated failure and provider-error contracts |
| Current, valid evidence | Active-revision snapshot and effective/expiry checks | Expired, future, inactive and revoked source cases |
| Source-bound answers | Server chunk lookup, evidence-type coverage and final current-ID recheck | Invented IDs, incomplete citation coverage and source changes during generation |

Both workflow engines execute the same nodes. The local engine is identified as `python`. Selecting LangGraph uses the SDK and LangChain StructuredTool; missing SDKs cause an explicit configuration failure. The local relevance check is lexical; hosted-model assessment uses structured provider output.

## Source governance and access

| Capability | Implementation | Verification |
|---|---|---|
| Server-owned identity | `backend/app/core/auth.py`, generated credential digests | Unauthenticated access, immutable principal and tenant/department scope |
| Structured Word import | `backend/app/services/parsing.py` | Body order, heading levels, list items, table cells and malformed/oversized files |
| Heading-aware, table-aware chunks | `backend/app/core/chunking.py` | Heading paths, bounded overlap, repeated table headers and complete rows |
| Change detection | Content SHA-256 plus title/access/evidence/date metadata | Unchanged publication skips embedding; metadata changes create a revision |
| Immutable revisions | `backend/app/services/store.py` | Version history, optimistic updates, concurrent-writer conflict and soft deletion |
| Authoritative source activation | Stage immutable vectors, then atomically switch the SQL active revision | Failed staging preserves the active version; retrieval excludes unactivated records |

SQLite owns the active revision and its allowed chunk IDs. External index results must belong to the authorized snapshot before their text reaches reranking. A failed publication can leave unreferenced index records, but they cannot enter retrieval through the active-revision allow-list. Publication coordination is scoped to a single application process.

## Retrieval and provider adapters

| Capability | Implementation | Verification |
|---|---|---|
| Local hybrid retrieval | Persisted feature-hashed vectors, BM25, RRF and lexical reranking | Real corpus retrieval and deterministic ranking checks |
| Milvus native hybrid retrieval | `MilvusHybridIndex`: dense vector, native BM25 and filtered RRF | Opt-in live test; requires a running service |
| Qdrant retrieval | Filtered dense search with authorized local BM25/RRF | Adapter code; live deployment remains a separate check |
| Embedding providers | `Embeddings`: local, Zhipu and OpenAI-compatible HTTP | Batch ordering and dimension/response validation |
| Zhipu reranking | `Reranker`: index/score validation and authorized candidates | Controlled HTTP contracts; live test is opt-in |
| Chat providers | `ChatModels`: Zhipu, DeepSeek and OpenAI-compatible endpoints | Structured-output schemas, bounded retries and sanitized errors |

An implemented adapter, a controlled provider contract and a verified live integration are separate evidence states. The default profile uses no remote model or external vector service.

## Inspection and evaluation

The React console provides a knowledge library, source editor, revision history, exact-source views, an ask workspace, execution traces and evaluations. Traces show search rounds, filters, candidate scores, relevance results, query revisions and stage timings.

The bundled regression dataset reports Recall@K, MRR, nDCG@K and keyword coverage. These metrics describe the small synthetic corpus. Source-ID validation and relevance assessment do not establish sentence-level faithfulness or production accuracy.

## Demonstration data

`bluewhale` exercises evidence-seeking answers; `bluewhale-kb` exercises source maintenance and department permissions. Each tenant has an independent policy set, so their thresholds and arrival rules must not be combined. `galaxy-retail` and `starlight` provide cross-tenant isolation scenarios. See [the corpus guide](../data/README.md) for the policy values and update inputs.

## Scope

The current application is single-turn and does not implement SSE, conversation memory, an MCP server, business-action tools, XLSX ingestion, automated human handoff, distributed ingestion workers or enterprise SSO. Refusal, source verification and operational traces are supported within those boundaries.
