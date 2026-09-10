import type { ChatAnswer, Evaluation, Trace } from './types'

const API = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!response.ok) throw new Error(await response.text())
  return response.json() as Promise<T>
}

export function chat(query: string, role: string): Promise<ChatAnswer> {
  return request('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ query, role, top_k: 5 }),
  })
}

export function getTrace(traceId: string): Promise<Trace> {
  return request(`/api/traces/${traceId}`)
}

export function runEvaluation(): Promise<Evaluation> {
  return request('/api/evaluate', { method: 'POST', body: JSON.stringify({ k: 5 }) })
}

export function ingestText(payload: {
  source_id: string
  title: string
  content: string
  allowed_roles: string[]
}): Promise<unknown> {
  return request('/api/documents/ingest-text', { method: 'POST', body: JSON.stringify(payload) })
}
