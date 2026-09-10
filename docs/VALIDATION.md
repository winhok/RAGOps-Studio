# Validation record

## Executed in the delivery environment

| Check | Result |
|---|---|
| Python test suite | **76 passed, 3 skipped** |
| Python application statement coverage | **86%** in the recorded local run; not branch coverage or an integration guarantee |
| TypeScript 5.8.3 strict build | Passed; compiled `frontend/dist` included |
| Python compileall | Passed |
| Browser behavior | **14 checks passed**, no browser JavaScript/console errors |
| Mobile layout | 390 px viewport checked for horizontal overflow; none observed |
| Current-version replacement | Browser update changed threshold from 3000 to 5000 and bound the next answer to the new revision |
| Duplicate publication | Browser resubmission returned a skip rather than a third revision |
| Scope boundaries | Unauthenticated, tenant, department, historical source and trace access tested |

Evidence files: `evidence/test-run.txt`, `evidence/pytest.xml`, `evidence/coverage.json`, `evidence/frontend-build.txt`, `evidence/browser-checks.json`, `evidence/environment.json`.

The browser ran the compiled application's real client logic against an isolated FastAPI process and SQLite state. This environment blocks browser navigation to localhost. The recorded browser run therefore used a local HTTP transport bridge: it loaded the built assets into Chromium, supplied an in-memory session-storage adapter for that blank-page context, and forwarded browser requests to the real local HTTP API. No canned RAG responses or fabricated application screenshots were used. This is **not** a claim of ordinary browser-network end-to-end or hosted-service validation.

## Explicitly not executed

The three skipped tests cover the real LangGraph/LangChain SDK execution, a running Milvus 2.6 service, and live Zhipu embedding/rerank/chat. The current environment has no installed optional SDKs, Docker engine, provider credentials, or usable package-network access. Milvus/Qdrant/DeepSeek/OpenAI-compatible remote integrations and clean-registry dependency installation are not certified by the local test result. HTTP provider contract tests use `httpx.MockTransport` and are identified as such in their file name.

Docker image/compose builds and GitHub Actions runs were not executed here. Their configuration files are supplied for use in an environment with the required services and network access.

## Repeat the checks

```bash
python -m pip install -r backend/requirements-dev.txt
python -m pytest -q
npm install --prefix frontend
npm run build --prefix frontend
python -m compileall -q backend/app
```

For ordinary browser testing on your machine:

```bash
python -m pip install playwright
python -m playwright install chromium
python scripts/check_browser.py
```

The browser script creates isolated temporary state and credentials, starts its own API process and cleans up after itself. It explicitly selects the local profile so it does not charge a configured cloud provider. `--transport-bridge` is only for restricted local-rendering environments and should be disclosed when used. `CHROMIUM_PATH` optionally selects an already installed Chromium binary.

For optional services, install `backend/requirements-integrations.txt` first. The LangGraph test then executes instead of skipping. With running local Milvus, set `RUN_MILVUS_TESTS=1` and optionally `MILVUS_URI`. For Zhipu, set `RUN_ZHIPU_TESTS=1`, `ZHIPU_API_KEY`, `CHAT_MODEL` and `EMBEDDING_MODEL`. That last test performs billable model requests. Live tests use isolated state/collections rather than the application's current dataset.

## Interpretation

A local pass demonstrates the application's state transitions, database operations, access boundaries, source checks, web interactions and selected provider contracts. It does not establish model quality, production scale, tenant isolation of an untested provider deployment, or faithful generation. The bundled benchmark is small synthetic regression data, not a publishable model-accuracy claim.
