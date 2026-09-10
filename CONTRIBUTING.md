# Contributing

Run `python -m pytest -q` and `npm run build --prefix frontend` before proposing a change. Keep external-service tests opt-in and label simulated HTTP transport tests as contracts, not live integrations. Add a regression test whenever changing source visibility, publication, evidence routing or citation validation.

Do not commit `.env`, `.secrets`, `.state`, provider keys, customer data or access tokens. Use only the supplied synthetic reference data in recorded examples. Keep scope mapped to `docs/REFERENCE-MAP.md`; do not add unrelated agent tooling as part of a bug fix.
