# Contributing

Run `python -m pytest -q` and `npm run build --prefix frontend` before proposing a change. Keep external-service tests opt-in and label simulated HTTP transport tests as contracts, not live integrations. Add a regression test whenever changing source visibility, publication, evidence routing or citation validation.

Do not commit `.env`, `.secrets`, `.state`, provider keys, customer data or access tokens. Use only the synthetic demonstration data in recorded examples. Keep changes consistent with `docs/architecture.md`; do not add unrelated agent tooling as part of a bug fix.
