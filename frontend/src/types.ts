export type Citation = {
  source_id: string
  title: string
  chunk_id: string
  quote: string
  score: number
}

export type ChatAnswer = {
  text: string
  citations: Citation[]
  trace_id: string
  confidence: number
  timings_ms: Record<string, number>
  route: string
}

export type Trace = {
  trace_id: string
  query: string
  role: string
  route: string
  confidence: number
  timings_ms: Record<string, number>
  retrieval: Array<{
    chunk_id: string
    source_id: string
    title: string
    dense_score: number
    lexical_score: number
    rrf_score: number
    rerank_score: number
  }>
}

export type Evaluation = {
  summary: {
    cases: number
    recall_at_k: number
    mrr: number
    ndcg_at_k: number
    keyword_coverage: number
  }
}
