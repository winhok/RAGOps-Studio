# Run and operate one RAGOps installation

## Local startup

Use the README commands from the repository root. In development, Vite serves the React console on port 5173 and proxies API calls to FastAPI on port 8000. For a production-style local run, build `frontend/dist` first; FastAPI then serves the compiled console and API from port 8000. Startup never silently seeds a database. Run bootstrap explicitly when the reference corpus is desired.

The credentials file holds five operator-generated accounts:

| Account | Scope | Purpose |
|---|---|---|
| agentic-admin | bluewhale / administrator | Five evidence-seeking scenarios from reference 08 |
| kb-admin | bluewhale-kb / administrator | Source lifecycle and department visibility |
| kb-support | bluewhale-kb / customer-service | Restricted employee queries |
| kb-finance | bluewhale-kb / finance | Finance-only evidence |
| starlight-admin | starlight / administrator | Separate tenant boundary |

`galaxy-retail` is seeded only as a cross-tenant negative-control corpus. It has no default interactive account. Existing credentials and existing source revisions are preserved on repeated bootstrap. To revoke access, remove its digest entry from the operator-owned registry; the file is resolved on each request. Do not expose the `.secrets` or `.state` directories through a web server.

## Switching embeddings or vector databases

Do not reuse vectors from a different model or dimensionality. Set a new `RAGOPS_STATE_DIR` **and** `VECTOR_COLLECTION`, then ingest the intended source files again. The state fingerprint rejects incompatible switches. A local restore requires the SQLite database and immutable source directory together. External indexes are additional state and must remain consistent or be rebuilt.

## Running the React console

Development mode:

```bash
npm install --prefix frontend
npm run dev --prefix frontend
```

Production build:

```bash
npm install --prefix frontend
npm run typecheck --prefix frontend
npm run build --prefix frontend
python scripts/serve.py
```

The frontend uses React 19, TypeScript 5.8 and Vite. TypeScript strict mode is enabled. The browser has no external CDN or font dependency. In the production topology, FastAPI serves the generated assets in `frontend/dist`; generated build output is intentionally not versioned. The Vite development server proxies `/api` and `/health` to the local backend. CORS configuration is not a substitute for authentication.

## Container commands

The Dockerfile uses a Node build stage for the React console and copies only `frontend/dist` into the final non-root Python image.

```bash
docker compose build
docker compose run --rm app python scripts/bootstrap.py --with-sample-data
docker compose run --rm app cat .secrets/access-credentials.txt
docker compose up -d
docker compose logs -f app
```

The plaintext credential command is for the local operator only. Named volumes retain application state and identities. The port is bound to loopback. The image runs one non-root worker; do not increase worker/replica counts without redesigning the publication lock and state coordination.

The optional `infra/milvus.compose.yml` is the local standalone integration stack with loopback port bindings. It retains local MinIO defaults for reproducibility. Do not publish these ports or reuse those credentials in a hosted service.

## Diagnostic approach

`GET /health` reports process readiness, not end-to-end model health. Run an authenticated query to verify the selected provider chain. A failure response includes a trace ID when workflow execution started. Use Execution traces to inspect the last completed decision/search stage; application logs intentionally omit raw questions, source bodies and provider keys.

A missing credential registry gives a configuration error. Missing SDKs fail on the selected integration rather than silently running the local provider. Provider 429/5xx failures are retried with bounded backoff; exhausted attempts return a safe 502 response. Invalid document metadata returns 400/422, forbidden writes 403, hidden sources 404, and stale version updates 409.

Request upload limit defaults to 2 MB, parsed content to 150,000 characters, per-document chunks to 400, and per-tenant active chunks to 5,000. The request-body middleware uses Content-Length when available; set a reverse-proxy body cap as well, especially for chunked transfer. PDF support is text extraction, not OCR. DOCX supports paragraph text, not an arbitrary document-conversion service.

## Public-hosting boundary

Before exposing an installation, validate it in that environment: HTTPS, proper secret delivery, authentication lifecycle, proxy request limits, backup/restore, live model/index connectivity and expected concurrency. This release deliberately does not implement a separate SSO platform, durable job queue, multi-node coordination or comprehensive monitoring suite.
