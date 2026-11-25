# Approved workflow inventory

Verified on 2026-11-25. The current local edition is **IntelliSure V2** on `http://127.0.0.1:8786`, with source on **codex/v2-stable**.

| Workflow | Local ID | Purpose | State |
| --- | --- | --- | --- |
| INSURANCE V2 — PRODUCTION | d9680d3641a921f8 | Claim intake, verification, preliminary analysis and platform callback | Published |
| INSURANCE V2 — AUDITED REPORT | 118d1a61ffbb12cd | Scoped analyst/auditor calls and publication gate | Published |
| INSURANCE V2 — READ ONLY REVIEW ASSISTANT | 492ef4d1806c4da8 | Optional user-triggered evidence reading | Published |
| INSURANCE V2 — REVIEW SYNCHRONIZATION | 5fc8604cdb2d6e48 | Versioned review-event synchronization | Published |
| INSURANCE V2 — LOCAL ERROR HANDLER | 7a7341255d9619a3 | Report production execution failures | Published |

All five live workflows match the sanitized node definitions and connections in `n8n/`. The main graph contains no disconnected executable nodes. The alternative LLM route remains connected and is retained; normal platform requests select local analysis. Zero historical executions alone is not evidence that an error handler, assistant or synchronization workflow is disposable.

## Cleanup performed

A consistent local n8n database backup and inventory were taken before cleanup. These two unpublished, unreferenced copies had no execution history and were archived through n8n's UI, removing them from the normal workflow list while retaining recovery:

- `6711e34d242f4052`: INSURANCE — شرح منظم (غير مفعّل).
- `fXrwOVKG2HhxQ9jm`: INSURANCE — TEST & DEVELOPMENT.

Seven older INSURANCE CORE/TEST workflows were already archived and remain archived. The old explanation export was moved from `n8n/insurance-explainer.json` to `docs/archive/insurance-explainer.json` as a historical reference; do not import or publish it alongside production.

The original `INSURANCE — PRODUCTION` and its three supporting workflows remain intact because the original application on port 8766 still targets them. They belong to the original edition, not V2. Other projects, credentials, saved claims and execution history were not modified. All five V2 workflows were retained.

## Verification

- Workflow contract checks passed: 122 total nodes including annotation cards, authenticated unique webhook routes, valid expressions and schema-constrained local model calls.
- Report engine: 29 tests passed.
- Isolated HTTP checks: 31 passed, including source scope, version conflicts, task concurrency and publication boundaries.
- Real pipeline: five bundled synthetic PDFs completed preparation and dispatch on the first attempt; main execution **2163** succeeded and audited report execution **2164** succeeded. The report reached **PUBLISHED** without an error.
- This is functional verification with synthetic data, not a measured guarantee of accuracy on arbitrary customer documents.

## GitHub and demo editions

- Approved V2 source: [codex/v2-stable](https://github.com/HamzaAlmughrabi02/insurance-intelligence/tree/codex/v2-stable).
- `main` retains the original local edition and its demo sources. It is not the V2 branch.
- Public demo: [IntelliSure demo](https://intellisure-insurance-demo.savorycord.chatgpt.site). It is a separate browser-local simulation with synthetic fixtures; it does not call n8n, OCR, PostgreSQL or the local V2 audited-report pipeline.
- The hosted demo's current Site version is 2, source commit `f3d88cbf7147cdc11bd3a43165776cb0a9cded5d` in the Site's separate source repository. That Site version number is unrelated to the product's V2 edition.
- Browser checks passed: load the five sample documents → run simulated analysis → open the exact review case → view original PDF and extracted text. No browser console errors were captured during these checks.

## تقديم المشروع

ابدأ من **INSURANCE V2 — PRODUCTION**، ثم انتقل إلى **AUDITED REPORT** لشرح التقرير. باقي Workflows خدمات مساندة تُستدعى عند الحاجة. استخدم [دليل العرض لعشر دقائق](PRESENTATION_10_MIN_AR.html) أو [صفحة Notion](https://app.notion.com/p/42328640055881b68012e3e9cadf5d5f). أسماء الطبقات والنودز بالإنجليزي والشرح بالعربي.
