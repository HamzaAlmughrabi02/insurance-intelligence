# IntelliSure V2 · Evidence review workbench

Independent development edition for motor-claim document review. The original local application and public demo remain separate.

## What changed

- Versioned structured reports with overview, findings, document comparison, reading coverage, follow-up tasks and revision differences.
- Exact document/page/span citations, highlighted text, side-by-side excerpts and a printable report with source text.
- Explicit unknown/partial/unreadable page coverage, uploaded-file hash checks, suggested document roles and reviewer overrides.
- General motor-part mentions, source-linked invoice rows, single-currency line arithmetic with explicit tax/discount rows, and explicit quantity/unit/line-total checks for supported pipe-separated layouts.
- Durable report queue and two local model calls inside a dedicated n8n workflow. Ollama native JSON-schema output, bounded context/output and no paid model dependency.
- Deterministic publication gate, case/version/execution scope, idempotent callbacks, report attempt snapshots, task revision CAS, and mandatory written reasons.
- Supplement uploads preserve original files and require a new analysis version. Current review cannot be approved while follow-up tasks are open or document-role changes require reanalysis.

## Publication policy and accuracy

Live synthetic QA found correlated semantic errors: the local analyst and local auditor could agree on a wrong paraphrase. V2 therefore does **not** automatically publish free model paraphrases. It publishes deterministic findings and, when all gates pass, model-selected text matching an original quotation. Other proposals remain explicitly withheld for human assessment. The free evidence assistant returns quotations rather than unsupported prose.

A JSON schema checks structure. Source matching checks provenance. Neither establishes factual authenticity, coverage eligibility or universal semantic accuracy. No certified accuracy percentage is claimed. A held-out, specialist-labelled real-document benchmark remains necessary before broadening automatic semantic publication.

Arithmetic is scoped to supported readable layouts and printed line amounts; it is not market-price validation or full table understanding. A lexical negation marker is labelled as text requiring context, not a proven contradiction. Suggested document roles are not authoritative classification.

## Current local deployment

| Service | Address |
|---|---|
| V2 website | http://127.0.0.1:8786 |
| V2 OCR reader | http://127.0.0.1:8787 |
| Shared n8n editor | http://localhost:5678 |
| Shared local Ollama | http://127.0.0.1:11434 |
| V2 PostgreSQL | insurance_ai_v2, dedicated insurance_v2 role |
| Original website | http://127.0.0.1:8766 |

Use the **IntelliSure V2** desktop shortcut. First use opens an expiring setup invitation; choose your own account/password. V2 has its own session cookie and account database. There is no default production password. The original shortcut remains available.

Daily flow: upload one motor-claim file set → wait for extraction and the main n8n analysis → wait for the separately tracked report audit → open findings and exact sources → resolve/assign follow-up tasks → upload supplements or correct document roles → reanalyze with a written reason → compare versions → record human review.

Closing/waiving a follow-up task records a reviewer action; it does not repair a document or authorize insurer coverage/payment. Role/supplement changes do not silently modify a saved report.

## Architecture

1. Python backend reads native PDF text, OCR and selectively grounded context.
2. V2 production workflow validates and persists the claim/analysis/review tasks, then returns the fixed snapshot.
3. A durable report job builds source-addressed evidence and deterministic checks.
4. `INSURANCE V2 — AUDITED REPORT` loads scoped evidence, calls the analyst, validates proposals, calls the semantic auditor and invokes the backend publication gate.
5. Error handling, review synchronization and read-only evidence search use separate V2 workflows and authenticated V2 webhook paths.

Models run locally. The reader may reuse the original installation's Python OCR environment/model caches, while document IDs, credentials, storage and service port remain isolated.

## Development and setup

This branch is `codex/intellisure-v2`; do not merge it into the original deployment without a migration review. Runtime secrets, uploads, accounts, databases, backups, QA fixtures and model weights are ignored by Git.

`configure_v2.py` prepares private local configuration. `prepare_v2_n8n.py` prepares five inactive workflow imports with fresh IDs and credential bindings. `deploy_local_v2.py` is a maintenance command for the existing Windows installation with its `insurance-postgres` container and n8n npm installation: it provisions only the V2 database/role, checks for active executions, backs up n8n, imports through its official CLI, publishes the V2 workflows and restarts n8n. `--report-only` and `--main-only` limit workflow updates. It is not a generic cloud installer. `compose.yaml` is a separate-container template using its own name/volume and port 5434; it is not used by the current shared-container deployment. Fresh standalone configuration uses 5434, while the already provisioned local V2 explicitly uses 5433. The local original backend/launcher must exist for that maintenance command; a standalone cloud deployment is outside this edition.

Install base requirements before development. OCR remains an optional separate environment, as documented in `docs/DOCUMENT_READER_AR.txt`. Do not reuse the original `.env`, `local-config.json`, accounts or claim storage for V2.

## Verification

```powershell
python test_accounts.py
python test_document_reader.py
python test_quality.py
python test_reliability.py
python test_v2_engine.py
python test_v2_http.py
node test_account_ui.js
node test_evidence_review.js
node test_review_center.js
node test_workflow_reliability.js
node test_reliability_ui.js
node test_v2_ui.js
node test_v2_workflows.js
```

These include real HTTP tests on isolated temporary data, deterministic/adversarial gate tests, UI contract checks and n8n expression/schema checks. The five bundled synthetic PDFs have also exercised the actual local preparation, PostgreSQL, n8n and report pipeline. Synthetic checks do not establish accuracy on arbitrary customer files. Browser QA uses a temporary synthetic account, never an owner account in V2.

The public static demo on the main branch remains an independent simulation and does not run this local V2 pipeline.

Arabic guides: [daily use](docs/V2_USER_GUIDE_AR.txt), [development study](docs/V2_DEVELOPMENT_STUDY_AR.html). The study describes the target design; the publication restrictions above reflect actual evaluation findings.
