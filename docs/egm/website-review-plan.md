# IntelliSure V2 website quality pass

## User intent and authorization
The user explicitly requested installing EGM, invoking independent experts, applying it to the website and implementing useful improvements. Existing accepted UI must remain recognizable; a previous replacement shell was rejected. Free tools only. This is an authorized review and targeted implementation pass, not an architecture replacement. Do not pause for routine tool selection. Escalate material business decisions or a proposed new design direction.

## Scope and current state
Active source is index.html plus ui-extension.js, auth-ui.js, evidence-review.js, review-center.js, reliability-ui.js, v2-report.js, employee-ui.css and existing supporting CSS. build_ui.py bundles the accepted UI into index.html. workspace.html/workspace-*.js are an inactive experiment: do not reactivate them. UI shows Arabic copy, RTL, a navigation rail, a report with six sections, source document viewer and reviewer follow-ups. Website uses account login, versioned API writes, exact evidence references and mandatory human review. Local V2 runs on 8786. Public demo is an independent older simulation, not the V2 report pipeline.

## Problem and goals
Review the implemented employee journey for concrete defects: navigation that loses context, stale requests, state-changing actions using wrong case/version, unexpected input loss, loading/error dead ends, inaccessible labels/focus and narrow-screen overflow. Preserve the accepted layout and palette; prioritize usability defects over ornamental redesign. Report findings only when grounded in cited code or reproduced UI behavior. A dormant node or a subjective style preference is not a defect by itself.

## Alternatives
1. Full frontend rewrite or enabling inactive workspace: rejected because it changes the user-approved layout and expands risk.
2. CSS-only cosmetic pass: insufficient for interaction/data-context errors.
3. Targeted changes to active modules, relevant regression tests and synthetic browser QA: selected. Existing routes, server validation, workflow graph and storage remain authoritative.

## Proposed implementation boundary
Modify only active frontend modules implicated by verified findings and their existing tests. Modify employee-ui.css only for focused legibility, responsive or keyboard defects. Regenerate index.html using build_ui.py. Create docs/egm/website-review-report.md to record reviewer outcomes and fix/contest decisions. No backend, workflow, credential, schema, claim data or model changes. Reviewers are strictly read-only and must not edit source.

## Expected interaction contract
- A result/source action must stay bound to the visible case and version; stale responses must not replace a newer route.
- Background refresh must not erase an employee's unsaved note, question, correction or task edits.
- Pending or failed reports show a truthful state, an available recovery action and no false approval affordance.
- Historical views remain read-only. Leaving history returns to the current evidence snapshot.
- Employees can identify the selected tab and operate controls with keyboard; narrow viewports do not cause document-level horizontal scrolling.
- Reuse current labels, API helpers and components. Escape all document/model text.

## Reviewer configuration
Target: full file docs/egm/website-review-plan.md. Run fresh-context Goldfish reviewers: design_critic against feature-spec-standard.md; codebase_details against implementation-readiness-standard.md; implementation_readiness against implementation-readiness-standard.md. Reading list: README.md, UX_IMPLEMENTATION.md, EMPLOYEE_UI_CHANGES_AR.md, build_ui.py, active frontend modules/styles, backend API contracts as needed, relevant tests. Do not read secrets, customer data, conversation history or memory. Each reviewer reports severity, file/line evidence, concrete failure and minimal repair; distinguish observations from proposed work.

## Verification and rollout
Before changes: inspect repository status and use isolated synthetic UI QA on 8788 with no background workers; never use owner credentials or record a real insurance decision. For each verified functional fix, reproduce a meaningful regression; run affected tests after patching and the established CI suite before final delivery. Rebuild the active bundle; browser QA exercises case navigation, report sections, evidence/source links, historical/current state, forms, loading/error and responsive layouts at 390px and desktop. Keep safety guards unchanged. Record what was and was not verified.

Rollback: restore the previous committed active frontend files and rebuild; no database migration is part of this change. Commit only reviewed source, tests and documentation to codex/v2-stable. Preserve original edition and public demo separation. Do not claim full EGM convergence from one review round; additional focused verification is validation, not a second fresh-context clean round.

## Resolved implementation plan
All three fresh reviewers completed. Accepted concrete fixes: guard delayed route openings and write completions; distinguish explicit report navigation from polling; preserve unsaved case/version/form drafts and focus; render scoped recoverable detail errors; retain keyboard focus when selecting evidence. Planning findings are accepted and resolved by this section.

Exact write allowlist (Modify): build_ui.py, ui-extension.js, auth-ui.js, evidence-review.js, review-center.js, reliability-ui.js, v2-report.js, .github/workflows/checks.yml; generated index.html. Create: review-state.js, test_review_interactions.js, docs/egm/website-review-report.md. Existing styles remain untouched. README may receive a documentation link only.

Phase 1: create review-state.js before active extension modules in the bundle. It owns a navigation generation, origin snapshots, in-memory dirty DOM drafts keyed by case/version and stable form identity. Delegated input/change events mark forms and review notes dirty; capture before replacement, restore the original dirty node after replacement, retain focus/selection/open disclosures. Drafts never use browser persistence and clear on account exit or case/version change. File selections are retained as the original input node, never reconstructed. Successful submission clears only that unchanged submitted draft; failed submissions retain it. Tasks carry the revision rendered with their form to preserve backend conflict checking.

Phase 2: invalidate pending case opens on all route changes. Explicit current/history report loads allocate a new request generation; polling reuses its generation. Async write/retry/correction completions refresh only their original still-visible route/report generation. Shared case-list refresh is allowed, but never assign an old currentId. Double submits are disabled; successful messages identify a completed save without forcing navigation.

Phase 3: detail errors replace initial loading with a scoped error and retry; a failed refresh retains already usable detail/drafts and adds recovery feedback. Stale errors cannot touch a different route. Evidence document/mode replacement restores keyboard focus to the equivalent new document/mode control.

Phase 4: add deferred-promise integration regressions in test_review_interactions.js (A/B inversion, home departure, history/current inversion, write finishing during navigation/history, rejected dependency/retry, draft isolation and submitted-only clearing). Browser checks use copied synthetic data: edit two follow-up forms, save one, switch tabs and verify the other survives; retain assistant question on detail refresh; switch evidence with keyboard; verify desktop and 390px layouts. Run the CI test commands from checks.yml; include the new regression in CI. Build, preserve current design, commit and push approved V2 source. No n8n or backend edit.

Process note: this is an adapted, user-authorized EGM review and repair pass. It is not the complete five-stage/two-clean-round EGM convergence protocol. Further review is optional and will not be labelled completed unless actually run.
