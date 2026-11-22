# Insurance Intelligence · IntelliSure

Local insurance document intake and preliminary claims review, with an Arabic interface, a Python backend, n8n and PostgreSQL.

**Local MVP, not a production certification or an automated coverage decision system.** Existing deployment tests do not establish accuracy for arbitrary customer documents.

## Included

- Arabic account setup/login, Argon2id password hashing, persistent HttpOnly sessions, CSRF protection and server-side reviewer roles.
- Multi-document intake, native PDF text extraction and limited XLSX extraction; images/scanned PDFs require manual review.
- In-page PDF/image preview, extracted-text view, Arabic review findings and text-matched source navigation.
- Versioned correction/reanalysis, audit history, durable dispatch jobs and idempotent callbacks.
- Sanitized production and explanation workflow templates, schema-only PostgreSQL initialization, prompt source and offline documentation.
- Windows launcher that reuses running services and opens the account UI.

The current web route uses local rules and document flags. `Basic LLM Chain1` is an alternative route and does **not** receive original document text. No external model is needed for the normal website route.

## Fresh Windows installation

Prerequisites: Python 3.11+, Node.js, an npm installation of n8n, and Docker Desktop. The workflow was exercised on n8n **2.8.4**; validate compatibility before upgrading. The frontend uses plain JavaScript/CSS, with no build framework or paid service.

Do not run fresh database provisioning over an existing deployment. Preserve its Docker volume, local configuration, uploads, SQLite database, and n8n installation.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe setup_local.py
docker compose up -d
```

Initialize your local n8n owner account once using `n8n.cmd start`, then follow the n8n setup screen. This login is separate from the website account.

Import the integration with locally generated credentials:

```powershell
.\.venv\Scripts\python.exe setup_n8n.py
```

This imports an **inactive** workflow; its local URL is saved in `local-setup-state.json`. Review it in n8n, check its PostgreSQL and Header Auth credentials, and publish it from the editor. If you use the alternative external-model path, configure its model credential separately. Do not activate the explanation copy beside production: its webhook paths are identical.

The original legacy webhook is retained in the template and lacks Header Auth. Keep this installation local; review or protect that entry point before any network exposure.

To create a Windows desktop shortcut:

```powershell
.\install_shortcut.ps1
```

Double-click **IntelliSure**. The launcher starts the existing PostgreSQL container and n8n when needed, starts the website, and opens a one-time account setup link. Choose your own username and password (at least 12 characters). There is no default website password. Later visits use your account or the remembered session, without entering API tokens.

## Network contract

| Component | Local address |
|---|---|
| Website | `http://127.0.0.1:8766` |
| n8n editor | `http://localhost:5678` |
| PostgreSQL from Windows | `127.0.0.1:5433` |
| PostgreSQL inside Docker | `5432` |
| Claim intake | `POST http://127.0.0.1:5678/webhook/insurance-web-intake` |
| Result callback | `POST http://127.0.0.1:8766/api/integrations/n8n/result` |

The backend extracts and persists source text before sending the n8n payload. n8n returns `{case_id, job_id, result}` using a separate callback credential. Website sessions never receive the integration tokens.

## Daily flow

Open IntelliSure → sign in → choose a motor claim → enter a client reference → upload all documents belonging to that claim → start analysis → review findings and source pages → correct with a reason and reanalyze when needed.

Document-source links derived from text matching are navigation aids, not verified evidence attribution. A missing policy database row is not proof that no policy exists. No automatic final coverage, liability or payment decision is made.

## Verification

```powershell
.\.venv\Scripts\python.exe test_accounts.py
node test_account_ui.js
node test_evidence_review.js
```

Account tests use isolated synthetic data; UI tests use a simulated DOM. These are not substitutes for authenticated browser review or independent model-quality evaluation. Node.js and a free localhost port are required for the relevant tests.

## Data and secrets

This repository intentionally contains **no** account database, claims database, uploaded customer files, live integration keys, session cookies, n8n credential exports, personal backups or execution logs. `database/schema.sql` contains schema only.

`setup_local.py` generates private `local-config.json` and `.env` files. `setup_n8n.py` creates ignored local credential/import files. Keep these private. Back up the live SQLite database consistently together with uploads, and back up PostgreSQL and n8n separately. The repository alone does not restore an existing deployment.

## Known limits

- Single-computer deployment; not a hardened public SaaS or multi-user administration product.
- No OCR; extraction patterns are limited and require human correction for unfamiliar documents.
- PostgreSQL review-task closure is not fully synchronized with the website review UI.
- No complete production malware scanning, file encryption or automatic cross-database backup policy.
- Native PDF display can depend on browser settings; extracted text remains available.

Offline Arabic documentation: [workflow guide](docs/WORKFLOW_GUIDE_AR.html), [platform connection](docs/PLATFORM_CONNECTION_AR.html), [layout preview](docs/LAYOUT_PREVIEW.html). Workflow links in these presentation snapshots refer to the original local installation; use the workflow ID generated for your installation.
