# Demonstration corpus

The company names and policies are synthetic demonstration data. They are not current business policies or customer data.

`bluewhale` and `galaxy-retail` exercise evidence-seeking retrieval and cross-tenant isolation. The refund review threshold is 2000 CNY and arrival is 1–3 working days. The inactive maintenance source supports the refusal scenario. Initial ingestion starts at revision 1.

`bluewhale-kb` and `starlight` exercise source maintenance, department permissions and tenant isolation. The initial refund review threshold is 3000 CNY; the update raises it to 5000 CNY. Arrival is 3–5 working days. Finance and customer-service policies have department-specific visibility.

The demonstration scenarios have independent policy sets in **different tenant namespaces**. A policy value in one tenant must not be used to answer questions in another. `updates/company-refund-v2.md` is an explicit update input; it is not auto-published.

`benchmark.json` is a small document-level synthetic regression set. It excludes open-ended business validation, live-model faithfulness and production accuracy. Changing the corpus intentionally can change its scores. Refusal and authorization are tested separately in the test suite.
