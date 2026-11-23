# Active design: original V2 interface

The previous V2 design was restored at the user request. Its CSS and layout remain the active design baseline from commit `3fac8481d40f253a192b82de50f415f1cac71da3`. Functional release fixes are documented in [RELEASE_ACCEPTANCE_AR.md](RELEASE_ACCEPTANCE_AR.md). The experimental workspace modules remain inactive for reference. No case data or original workflow was reverted.

---

The following describes the inactive experiment:

# V2 case workspace

The case list now identifies the client, current version, review reason and next action. A single case route serves entry from every list or legacy review link. Its four sections are Report, Evidence, Follow-up and History. Source text, exact quotations and original PDF/image previews open beside the report.

Creation uses one file picker/drop area, with folder import behind an advanced disclosure. Upload retries retain the draft identifier and successful uploads in memory. Client references and form entries survive navigation within the current signed-in page session; reloads clear unsaved entries. No customer data or credentials are stored in browser storage.

`backend/workspace_api.py` provides a read-only current-version projection. Existing authenticated write endpoints, CSRF, version checks, task revision checks and report evidence gates remain authoritative. The UI explains why approval is unavailable, offers note-only report updates and keeps historical reports read-only. Processing updates pause visual replacement while the user edits a form.

Build: `python build_ui.py`. Sources: `workspace.html`, `workspace.css`, `workspace-state.js`, `workspace-auth.js`, `report-views.js`, `workspace-reader.js`, `workspace-ui.js`. Legacy view files remain for rollback/reference and are not bundled. No additional frontend dependency or hosted service is required.

Validation: all 15 existing and new local test suites passed. Browser QA used a copied synthetic fixture on port 8788 without workers: list and case navigation, source text and original preview, current/old version navigation, blocked approval, form preservation, creation-field preservation, mobile layout at 390px (no document overflow), and no console errors. HTTP regressions cover authenticated workspace access, missing case, draft state and the existing report/task/version guardrails. No real claim decision was submitted during UI QA.

Activation: V2 backend only on port 8786. The original edition and its workflows were not modified. Source and consistent SQLite backups are under ignored `backups/ux-flow-*`. Runtime data, configuration, secrets and QA accounts are excluded from Git.
