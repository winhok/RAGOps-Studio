export class ApiError extends Error {
    status;
    traceId;
    constructor(message, status, traceId) {
        super(message);
        this.status = status;
        this.traceId = traceId;
    }
}
let credential = sessionStorage.getItem('ragops.credential') || '';
export function setCredential(value) {
    credential = value;
    if (value)
        sessionStorage.setItem('ragops.credential', value);
    else
        sessionStorage.removeItem('ragops.credential');
}
export function hasCredential() { return !!credential; }
export async function api(path, options = {}) {
    const headers = new Headers(options.headers);
    headers.set('Authorization', `Bearer ${credential}`);
    if (options.body && !(options.body instanceof FormData))
        headers.set('Content-Type', 'application/json');
    const response = await fetch(path, { ...options, headers });
    const data = await response.json();
    if (!response.ok) {
        const detail = typeof data.detail === 'string' ? data.detail : Array.isArray(data.detail) ? data.detail.map((e) => e.msg).join('; ') : '';
        throw new ApiError(data.error?.message || detail || 'Request failed', response.status, data.error?.trace_id);
    }
    return data;
}
