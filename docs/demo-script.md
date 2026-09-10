# 90-second Loom demo script

**0–15s — problem**

> Most RAG demos show a chatbot, but production failures usually happen around retrieval quality, stale documents, permissions, and debugging. I built RAGOps Studio to make those parts visible.

**15–35s — query and citations**

Ask: `When should support open a carrier investigation?`

> The pipeline filters the active knowledge base by role, runs BM25 and dense retrieval, fuses both rankings with RRF, reranks the candidates, and returns a grounded answer with citations.

**35–55s — trace inspector**

Open the trace tab.

> Every request has a trace ID. I can inspect dense score, lexical score, RRF score, rerank score, and stage latency. That gives me a concrete place to debug retrieval failures.

**55–70s — ACL/versioning**

Switch to the knowledge page.

> Documents are versioned and deduplicated by checksum. There is also role-aware retrieval: internal escalation policy is not part of a public user's candidate set.

**70–85s — evaluation**

Run the benchmark.

> I also treat evaluation as part of the product. The included benchmark reports Recall@K, MRR, nDCG, and answer keyword coverage, so retrieval changes can be regression-tested.

**85–90s — close**

> The repository is public and the stack is FastAPI, LangGraph, React, TypeScript, with optional Qdrant and OpenAI-compatible providers.
