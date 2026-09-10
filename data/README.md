# Reference corpus

The company names and policies are synthetic data supplied in the two reference projects. They are not current business policies or customer data.

`bluewhale` and `galaxy-retail` reproduce the **08-agentic-rag** evidence scenario. The threshold is 2000 CNY and arrival is 1–3 working days. The inactive maintenance source is retained for the refusal scenario. Imported revisions start at 1; the reference fixture's historical version numbers are not fabricated as a new revision history.

`bluewhale-kb` and `starlight` reproduce the **12-enterprise-knowledge-base** Markdown scenario. The initial threshold is 3000 CNY; the supplied update raises it to 5000 CNY. Arrival is 3–5 working days. Department-only finance and customer-service policies are preserved.

The two source projects use the same company name with different rules. They are deliberately placed in **different tenant namespaces**, not merged into a contradictory policy. The Starlight tenant demonstrates cross-tenant isolation. `updates/company-refund-v2.md` is an explicit update input; it is not auto-published.

`benchmark.json` is a small document-level synthetic regression set. It excludes open-ended business validation, live-model faithfulness and production accuracy. Changing the corpus intentionally can change its scores. Refusal and authorization are tested separately in the test suite.
