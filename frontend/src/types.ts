export interface Principal {
    user_id: string;
    name: string;
    tenant_id: string;
    department_id: string;
    role: 'admin' | 'employee';
}
export interface Runtime {
    graph_engine: string;
    model_provider: string;
    embedding_provider: string;
    rerank_provider: string;
    vector_backend: string;
    dimensions: number;
    max_searches: number;
    chat_model: string;
    embedding_model: string;
}
export interface Session {
    principal: Principal;
    runtime: Runtime;
}
export interface DocumentRecord {
    id: string;
    revision_id: string;
    title: string;
    tenant_id: string;
    version: number;
    checksum: string;
    department_id: string;
    visibility: string;
    evidence_type: string;
    additional_evidence_types: string[];
    effective_at: string;
    expires_at: string | null;
    source_path: string;
    active: boolean;
    created_at: string;
    chunk_count: number;
    content?: string;
}
export interface Citation {
    chunk_id: string;
    document_id: string;
    title: string;
    version: number;
    chunk_index: number;
    evidence_type: string;
    content: string;
    source_path: string;
    source_url: string;
}
export interface ChatAnswer {
    text: string;
    citations: Citation[];
    trace_id: string;
    outcome: string;
    route: string;
    search_attempts: number;
    required_evidence: string[];
    missing_evidence: string[];
    stop_reason: string;
    timings_ms: Record<string, number>;
    runtime: Runtime;
}
export interface Candidate {
    chunk_id: string;
    document_id: string;
    title: string;
    version: number;
    evidence_type: string;
    content: string;
    dense_score: number | null;
    lexical_score: number | null;
    rrf_score: number | null;
    rerank_score: number | null;
    source_path: string;
    effective_at: string;
    expires_at: string | null;
}
export interface SearchRound {
    attempt: number;
    evidence_type: string;
    query: string;
    scope_count: number;
    permission_filter: string;
    timings_ms: Record<string, number>;
    candidates: Candidate[];
}
export interface Trace {
    trace_id: string;
    query: string;
    outcome: string;
    route: string;
    search_attempts: number;
    stop_reason: string;
    required_evidence: string[];
    missing_evidence: string[];
    events: {
        node: string;
        message: string;
        missing?: string[];
    }[];
    searches: SearchRound[];
    rejected: {
        chunk_id: string;
        reason: string;
    }[];
    timings_ms: Record<string, number>;
    runtime: Runtime;
    error_code?: string;
}
export interface Evaluation {
    summary: {
        cases: number;
        recall_at_k: number;
        mrr: number;
        ndcg_at_k: number;
        keyword_coverage: number;
    };
    cases: {
        query: string;
        outcome: string;
        recall_at_k: number;
        reciprocal_rank: number;
        ndcg_at_k: number;
        keyword_coverage: number;
        trace_id: string;
    }[];
    metric_scope: string;
    dataset: string;
    runtime: Runtime;
    k: number;
}
