# Architecture and operational invariants

## Request path

```mermaid
flowchart TD
    UI[Typed web client] --> API[FastAPI + server-issued principal]
    API --> Decide[Decide: direct / clarify / retrieve]
    Decide --> Direct[Text-only response]
    Decide --> Clarify[Ask for missing user input]
    Decide --> Scope[SQL current revision + tenant/department scope]
    Scope --> Retrieve[Dense + BM25 → RRF → rerank]
    Retrieve --> Assess[Assess relevance, missing evidence, status and dates]
    Assess -->|Missing type and budget remains| Scope
    Assess -->|Previously searched type still missing| Revise[Revise query once within search budget]
    Revise -->|Distinct query| Scope
    Revise -->|No alternative| Refuse
    Assess -->|Complete| Generate[Generate structured answer]
    Assess -->|No new evidence or budget exhausted| Refuse[Refuse]
    Generate --> Bind[Bind IDs; check evidence coverage; revalidate current access]
    Bind --> Result[Answer + source records + trace ID]
```

The iteration is evidence-seeking, not an unconstrained autonomous agent. By default at most three searches run. The graph does not call business APIs or execute external side effects. A request is single-turn: after clarification, the user resubmits the question with the missing input. Conversation memory and SSE are not implemented.

Before relevance assessment, candidate chunks must pass tenant/department access, current revision, validity dates and requested evidence-type checks. The local profile uses a disclosed lexical overlap check; the hosted-model profile asks for a strict list of supporting chunk IDs. Unknown IDs or provider failures stop the request safely. This judgment checks relevance, not sentence-level entailment or factual truth.

If a previously searched evidence type is still missing and its authorized scope is nonempty, the workflow may revise the query once per request. Equivalent queries are not searched again, each retrieval still counts toward `max_searches`, and another unsuccessful search ends in refusal. Partial relevant evidence is retained so a revision cannot bypass required-type coverage. Assessments are cached per chunk for the current request. Trace summaries are written by the server rather than persisting model-generated explanations that might restate revoked source text.

Word import uses the existing local parser dependency. It keeps paragraph/table order, headings and list items. Tables are stored as Markdown with their first row as the header; repeated headers accompany each table chunk. DOCX expansion is bounded and a row too large for a complete chunk is rejected before publication. Images, OCR, page layout and exact Word numbering are outside this parser's scope. No extra service or storage engine is required.

## Publication path

1. Resolve the administrator from the server credential registry.
2. Validate title, access metadata and timezone-aware validity dates. Normalize Markdown line endings and compute its checksum.
3. Compare against the **active** revision's content and metadata. A previous historical checksum is not considered a no-op.
4. Parse heading-aware chunks. Assign immutable source/chunk identities and generate embeddings once.
5. Stage new chunk IDs in the vector index. They are not yet eligible for retrieval.
6. Write an immutable source file. Use a SQL transaction and an optimistic version precondition to activate the new revision and deactivate the old one.
7. Subsequent retrieval snapshots contain only the new revision. Old source versions remain administrator-readable.

A stage/write failure leaves the old SQL revision active. This is not a distributed transaction or an exactly-once external guarantee. A failed run can leave unreferenced vector records or a source file; the SQL allow-list prevents those records from being used. Rebuilding into a new state/collection is the supported maintenance path for this small installation.

## Access boundary

`tenant_id`, `department_id`, and `role` are never accepted in chat or document bodies. The credential maps to a server-owned principal. Both BM25 and dense retrieval consume the same authorized snapshot. External vector results are checked against that snapshot **before** any text goes to reranking or answer generation.

An administrator can manage their own tenant only. An employee sees company-wide documents and their department's sources. An employee cannot browse historical source revisions, write documents or run the administrator's regression dataset. Traces are restricted to their owner or a same-tenant administrator. Old employee trace bodies and answers are redacted when cited access is revoked.

Authorization is checked again immediately before releasing a cited answer. Data already sent to a remote model during an authorized in-flight request cannot be retroactively withdrawn; this application does not claim otherwise.

## Source validation is deliberately narrower than truth evaluation

The server rejects invented IDs, missing evidence-type coverage and superseded/unauthorized sources. It cannot establish that every generated sentence is entailed by those sources. The local profile quotes retrieved text; the hosted-model profile uses a constrained JSON prompt. Neither is advertised as a proof of factual faithfulness.

## Runtime adapters

- `local`: persisted feature-hashed vectors + BM25 + RRF + lexical reranker, rule router and extractive answerer. No hidden fake success response.
- `milvus`: native dense vector + BM25 sparse function with identical pre-search filters and RRF. Individual leg scores are `null` when the SDK returns only a fused score; the UI shows a dash instead of inventing values.
- `qdrant`: filtered dense ANN with authorized local BM25 and RRF. Preserved compatibility path.
- `langgraph`: the actual StateGraph and StructuredTool over the shared nodes.
- Zhipu: embeddings, rerank and chat. DeepSeek: chat/decision. OpenAI-compatible adapter: preserved embeddings/chat path.

Provider requests have bounded timeouts and retry only transient network errors, HTTP 429 and 5xx. Auth failures are not retried. Provider response bodies and keys are not echoed into user-facing errors. Completed stages survive a later generation failure in the trace.
