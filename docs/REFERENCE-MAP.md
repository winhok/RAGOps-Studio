# Reference scope and implementation map

Only the two uploaded references defined **new functionality** for this release. The existing RAGOps core was retained where compatible; it was not replaced with the reference applications wholesale.

## 08-agentic-rag

| Supplied code / concept | Integrated implementation | Check |
|---|---|---|
| `workflow.js`: structured request decision | `services/graph.py`, `core/models.py`, provider decision schemas | Direct, clarify and retrieval cases |
| `models.js`: structured model output | `services/providers.py`: DeepSeek/Zhipu JSON requests and Pydantic validation | Invalid JSON, unknown evidence type, source-ID tests |
| `search_knowledge` LangChain tool | `RetrievalTool`; principal bound by server closure; optional real `StructuredTool` | Tool rejects client-supplied tenant or role |
| Required evidence / additional searches | Bounded decide → search → assess → generate loop | Multi-source search order; search budget; no-new-evidence stop |
| Active version and dates | SQL current-revision snapshot and effective/expiry checks | Expired/future/inactive source cases |
| Source IDs cover all evidence types | Server lookup, type coverage and post-generation current-ID recheck | Invented IDs, partial coverage and source-change refusal |
| `knowledge.js`: local fixture search | Replaced by actual BM25/vector/RRF/re-rank retrieval over persisted sources | Actual index scores and document revisions |
| Five supplied scenarios | `data/fixtures/bluewhale`, `test_agent_workflow.py` | Direct, single, multi, clarify, unknown |

The Python state-machine executor and the optional LangGraph executor use the same workflow nodes. The local executor is identified as `python`, not represented as a LangGraph run. The LangGraph path calls the real SDK and LangChain StructuredTool; it fails at startup when the selected SDK is missing.

## 12-enterprise-knowledge-base

| Supplied code / concept | Integrated implementation | Check |
|---|---|---|
| `auth/demo-users.ts` and server principal | `core/auth.py`, random operator-issued credentials from bootstrap | 401, immutable server-owned role/tenant, scoped access |
| `milvus/filter.ts`: company/department ACL | SQL-authorized snapshot plus tenant/department expression on both ANN legs | Cross-tenant/department denial and prompt-input isolation |
| Markdown AST chunking and headings | `core/chunking.py` | Heading path, code text, bounded length and overlap |
| `documents/document.service.ts`: change detection | Content SHA-256 plus access/title/evidence/date metadata comparison | Same source skips embedding; ACL change creates revision |
| Immutable version files / update / delete | `services/store.py`, optimistic version preconditions | New version only; old revision retained; concurrent writer conflict; soft delete |
| Milvus dense + native BM25 + RRF | `MilvusHybridIndex`: BM25 function, jieba analyzer, two filtered searches, RRFRanker | Live test provided; not represented as executed without service |
| Zhipu embedding and index alignment | `Embeddings`: batch order/dimension validation | Mock HTTP contract checks; live test separate |
| Zhipu reranking | `Reranker`: index validation and actual provider score mapping | Invalid indexes, authorized-only inputs |
| Source-bound JSON answer | `generate_answer`: IDs resolve to stored chunk records | Citation invalidation and exact source endpoint |
| Source/version maintenance UI | Knowledge library + editor + history + source views | Browser behavior checks and authenticated API tests |

## Integration choices, not additional product features

A single document may cover more than one required evidence type. The supplied enterprise refund Markdown includes both review and arrival rules, so it is tagged as `review_rule` with `arrival_rule` as an additional type. The agentic fixture has separate source documents. This preserves the supplied facts without forcing duplicate documents or refusing a supported arrival question.

The two references disagree on the Bluewhale refund threshold and arrival time. Their datasets therefore occupy separate tenant namespaces: `bluewhale` for reference 08, `bluewhale-kb` for reference 12. The latter update document remains an explicit user action. Historical fixture version numbers are not invented as publication history in a new database.

Instead of toggling current flags across SQLite and Milvus independently, new immutable vectors are staged first. SQLite atomically switches the active revision; its allowed chunk IDs constrain all searches. A failed publication can leave orphan vectors, but those IDs are never retrievable until an authoritative SQL publication exists. This is bounded to one process and a small per-tenant authorized snapshot.

## Retained from the previous RAGOps codebase

TXT / text-based PDF / DOCX parsing; Qdrant dense retrieval with local BM25/RRF; OpenAI-compatible HTTP adapters; Recall@K, MRR, nDCG@K, keyword coverage; trace IDs and timing visibility. These are not attributed to the two new references.

## Not added in this change

MCP server/business tools, SSE streaming, cancellation, XLSX ingestion, automated human handoff, Telegram, daily summaries, and Faithfulness scoring are not implemented here. A LangChain StructuredTool is not an MCP server, a refusal is not a human-handoff integration, and source-ID validation is not semantic faithfulness evaluation.
