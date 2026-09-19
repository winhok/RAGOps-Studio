# 90-second capability walkthrough

Use a running installation, not a fabricated output. Do not show credentials, provider keys, `.env`, private documents or customer names.

## 0–25 seconds: evidence-seeking answer

Sign in as `agentic-admin`. Open Ask workspace and run:

> 订单 A2026 的咖啡机退款金额是 3500 元，需要人工审核吗？准备材料时还要注意什么？

Show the two source cards, open one exact source, then open the trace. The workflow should retrieve the review rule first, identify `material_requirement` as missing, run one more retrieval, then bind the answer to both sources.

Suggested narration: "This workflow doesn't retrieve the whole knowledge base for every question. It looks for the evidence it needs, checks what's missing, and stops once the answer can be tied to current sources."

## 25–40 seconds: clarify and refuse

Run the preset without an amount. It should ask for the missing amount without searching. Run the maintenance preset; the historical source is inactive, so the workflow refuses rather than promising a lifetime benefit.

Suggested narration: "Missing user input becomes a clarification. Missing authorized evidence becomes a refusal. Those are different states, not exceptions hidden behind a generic answer."

## 40–65 seconds: permissions

Switch to `kb-support` without recording the credential. Ask `财务负责人需要复核哪些信息？`. It should refuse. The library should show company-wide and customer-service documents, not finance or another tenant's policies. Switch to `kb-admin` and ask the same question; it should cite the finance source.

## 65–90 seconds: publication and inspection

As `kb-admin`, edit `company-refund` and replace its Markdown with `data/updates/company-refund-v2.md`. Keep `arrival_rule` in its additional evidence types. Publish, ask the threshold question, and verify that the response now cites v2 with 5000 CNY. Version history retains v1 with 3000 CNY. A second identical publish should be skipped.

The source-maintenance scenario uses `bluewhale-kb`; the evidence-seeking scenario uses `bluewhale`. These tenants have independent policy sets. Switching tenants does not represent a policy change; publishing a replacement revision does.

## Runtime disclosure

When using the default local profile, say: "This recording uses the reproducible local execution profile. The API, retrieval, permissions, revisions and traces are live. The configured GLM/Milvus/LangGraph path is separate." Only call it a live hosted-model run after enabling and verifying those integrations.

## Document-to-citation demonstration

Generate a synthetic Word source on the machine used to open the console:

```bash
python scripts/create_demo_document.py /tmp/ragops-document-demo.docx
```

The generator refuses to overwrite an existing file. As an administrator, add a document titled `Document retention standard`, select evidence type `general`, and upload the generated file. Open the stored source to show its heading hierarchy, list items and table. Ask:

> What is the retention period for demonstration uploads?

The answer should include `30 days`; open the citation that contains the table and show its exact source revision. In the trace, each search round shows supporting/excluded candidates and the assessment method. The default profile explicitly displays `Local lexical check`; this is not a semantic model-quality demonstration.

For a verified hosted-model profile, relevance assessment uses the configured chat model. When a search lacks supporting evidence, the trace can show one alternative query, followed by another search within the existing budget. Do not promise that every question triggers a revision: complete evidence proceeds directly, an empty authorized scope stops, and an equivalent alternative is not searched again. Provider failures remain explicit failures. Controlled regression cases exercise rejection, successful revision, repeated failure, duplicate queries, revocation and search-budget limits; they are workflow-contract evidence, not live model-accuracy results.
