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

The two source projects have conflicting Bluewhale examples, so this enterprise lifecycle scenario uses `bluewhale-kb`; the agentic scenario remains in `bluewhale`. Explain this as corpus separation rather than implying a single business changed policy between scenes.

## Runtime disclosure

When using the default local profile, say: "This recording uses the reproducible local execution profile. The API, retrieval, permissions, revisions and traces are live. The configured GLM/Milvus/LangGraph path is separate." Only call it a live hosted-model run after enabling and verifying those integrations.
