# Changelog

## 0.2.0 — Reference integration

- Connected evidence-seeking decisions and bounded follow-up retrieval to the persisted knowledge base.
- Added server-issued tenant/department identities, authenticated APIs, administrator document maintenance and source revalidation.
- Added Markdown heading paths, active-revision change detection, immutable sources, expected-version updates and soft deletion.
- Added native Milvus hybrid and Zhipu/DeepSeek adapters; retained explicit local and existing compatibility backends.
- Replaced the React build shell with a small typed browser client and included its compiled assets.
- Added behavior/security/provider-contract tests and explicit opt-in live integration checks.
- Replaced the previous synthetic corpus with the two supplied scenarios in separate namespaces; removed outdated auto-seeding and unqualified production claims.

There is no automatic migration from a v0.1 database. Keep the old package intact and use a new state directory. No previous private data is bundled in this release.
