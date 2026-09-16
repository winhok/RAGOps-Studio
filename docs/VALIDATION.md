# Validation record

## Current GitHub Actions validation

The React/Vite refactor is verified from source on GitHub Actions rather than relying on committed build artifacts.

| Check | Result |
|---|---|
| Frontend dependency install | Passed on Node 22 |
| npm high-severity audit gate | **0 vulnerabilities** in the recorded PR run |
| React + TypeScript + Vite production build | Passed with Vite 8.3.0 |
| Python test suite | **76 passed, 3 skipped** |
| Python compileall | Passed |
| LangGraph adapter job | Passed with LangGraph/LangChain installed |
| Static bundle integration | Passed after Vite build; FastAPI served the generated hashed JS/CSS assets |

The three skips in the ordinary application test job are intentional integration gates for LangGraph SDK availability, a running Milvus service, and live Zhipu requests. LangGraph is exercised separately in its dedicated CI job and currently passes. Milvus and Zhipu remain opt-in because they require an external service or billable provider access.

## Recorded browser workflow validation

Before the React/Vite architecture refactor, the same workspace behavior and FastAPI contracts were exercised in Chromium against an isolated local API state:

| Check | Recorded result |
|---|---|
| Browser behavior | **14 checks passed**, no browser JavaScript/console errors |
| Mobile layout | 390 px viewport checked for horizontal overflow; none observed |
| Current-version replacement | Browser update changed threshold from 3000 to 5000 and bound the next answer to the new revision |
| Duplicate publication | Browser resubmission returned a skip rather than a third revision |
| Scope boundaries | Unauthenticated, tenant, department, historical source and trace access tested |
| Python application statement coverage | **86%** in the recorded local run; not branch coverage or an integration guarantee |

Those screenshots and browser evidence remain useful for the workflow itself, but they must not be read as a fresh end-to-end browser run of the React refactor. The React refactor preserves the same IDs, data attributes, API contracts and user flows, and `scripts/check_browser.py` has been updated to discover Vite's hashed production bundles. Re-run the browser suite locally before replacing the screenshots or claiming React-specific browser validation.

The recorded browser run used the compiled application's real client logic against an isolated FastAPI process and SQLite state. In the restricted authoring environment, a local HTTP transport bridge forwarded browser requests to the real local HTTP API. No canned RAG responses were used. That run was not a hosted-service validation.

## External integrations not certified by the main CI job

The default CI path does not certify:

- a running Milvus 2.6 service,
- live Zhipu embedding/rerank/chat,
- Qdrant / DeepSeek / other remote provider deployments,
- Docker image or Compose startup in a hosted environment.

Provider contract tests use controlled HTTP transports and are not presented as live integrations. Live provider checks remain explicit opt-in tests because they require credentials and may incur cost.

## Repeat the checks

```bash
python -m pip install -r backend/requirements-dev.txt
npm install --prefix frontend
npm audit --prefix frontend --audit-level=high
npm run typecheck --prefix frontend
npm run build --prefix frontend
python -m pytest -q
python -m compileall -q backend/app
```

For ordinary browser testing on your machine:

```bash
python -m pip install playwright
python -m playwright install chromium
python scripts/check_browser.py
```

The browser script creates isolated temporary state and credentials, starts its own API process and cleans up after itself. It explicitly selects the local profile so it does not charge a configured cloud provider. `--transport-bridge` is only for restricted local-rendering environments and should be disclosed when used. `CHROMIUM_PATH` optionally selects an already installed Chromium binary.

For optional services, install `backend/requirements-integrations.txt` first. With running local Milvus, set `RUN_MILVUS_TESTS=1` and optionally `MILVUS_URI`. For Zhipu, set `RUN_ZHIPU_TESTS=1`, `ZHIPU_API_KEY`, `CHAT_MODEL` and `EMBEDDING_MODEL`. Live tests use isolated state/collections rather than the application's current dataset.

## Interpretation

The CI pass demonstrates that the React console builds from source, the generated bundle is served by the FastAPI application, backend state transitions and access rules pass the regression suite, and the LangGraph adapter executes in its dedicated dependency job. It does not establish model quality, production scale, hosted-service reliability, or answer faithfulness. The bundled benchmark is small synthetic regression data, not a publishable model-accuracy claim.
