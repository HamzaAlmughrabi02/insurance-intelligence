# EGM website review and repair

## Execution evidence
- Official plugin: google/elephant-goldfish-model, version 0.1.1; inspected source commit 63e239d8d4c3ddc6774faf533b4997405f78c549.
- Complete plugin installed through Codex marketplace commands, including bundled personas and standards. Available to the skill picker on the next turn.
- Target: website-review-plan.md, originally lines 1–34; a resolved implementation plan was appended after review.
- Three native reviewer agents launched with fork_turns=none. Conversation history was not passed; filesystem/instruction-file isolation is not certified.
- Reviewers: design_critic / feature-spec-standard; codebase_details / implementation-readiness-standard; implementation_readiness / implementation-readiness-standard. All three completed and reported source reads. No reviewer was counted as completed merely for being launched.
- This is an adapted, user-authorized single review and implementation pass. Full five-stage EGM review and two consecutive clean rounds were not run; no convergence claim is made.

## Findings and decisions
| ID | Reviewer(s) | Severity | Finding | Resolution |
| --- | --- | --- | --- | --- |
| route-1 | all three | Major | Delayed case opens override newer case/home navigation | FIX: navigation generations; stale completions ignored before state/history changes |
| report-1 | codebase_details | Major | Historical response can replace a newer return-current request | FIX: explicit current/history navigation owns a new request generation; polling reuses its generation |
| write-1 | design_critic, codebase_details | Major | Save/retry/correction/review completions replace a newer route or historical view | FIX: capture origin route/report request and refresh only while it is still current |
| draft-1 | all three | Major | Saving one follow-up or background detail refresh erases other unsaved forms/questions | FIX: transient per-case/version dirty DOM drafts; retain only unsaved forms, original file input nodes, open disclosures and focus; clear on account exit/scope changes |
| recovery-1 | all three | Major | Failed detail dependency leaves permanent loading without retry | FIX: scoped error and retry, retain usable existing detail on refresh failure |
| keyboard-1 | implementation_readiness | Major | Replacing evidence controls discards keyboard focus | FIX: restore focus to selected document or mode control |
| plan-1 | codebase_details, implementation_readiness | Major | Review charter lacks exact file boundaries and algorithms | FIX: append exact Modify/Create allowlist, phases, state ownership and concrete regressions before code changes |
| test-1 | design_critic | Nit | Concurrency scenarios not explicit in initial plan | FIX: delayed A/B, history/current, save/navigation and unrelated-draft scenarios recorded and tested |

## Focused post-fix validation
The codebase reviewer completed a second, focused validation pass (not a fresh Goldfish round). It identified three additional edge cases, all repaired and verified by that reviewer: edits made during an acknowledged task save now retain the advanced task revision; an old case's save cannot clear a different case's same-key draft; restored dirty forms receive the current read-only lock after restoration. Added regressions for the first two; existing report lock behavior remains in force.

## Implementation boundaries
Accepted navigation rail, layout, palette and components remain unchanged. No backend, database, workflow or insurance-decision rule changed. New review-state.js is bundled before active extensions. Drafts stay in page memory, use no localStorage/sessionStorage and disappear on reload/account exit or case/version scope change. Server-side version, revision, permission and evidence checks remain authoritative. Task drafts retain their originally rendered revision so concurrent edits still fail safely at the backend.

## Browser verification
Copied synthetic claim only, isolated QA server on 8791, no workers or owner session. Edited two follow-up forms; saved the first without closing a task or recording a coverage/review outcome. The second retained owner and unsaved reason. Switched report tabs and verified that draft survived. Typed an assistant question and switched evidence using Enter; keyboard focus remained on the selected text control. Desktop and 390px inspection found no document-level horizontal overflow. Browser console captured no errors.

Browser failure injection, actual network out-of-order traffic and background synchronization timing were not simulated in the browser; deterministic Node regressions cover the corresponding request/draft logic. Original-file picker restoration during a rerender is implemented through DOM-node retention but was not exercised with a live file chooser in this pass.

## Regression verification
New test_review_interactions.js covers out-of-order case opens, departure to home, current/history and history/history inversion, saves completing after historical/route navigation, each detail dependency failure and retry, stale errors, independent dirty drafts/focus and case/account clearing, and retry completion after opening another case. Existing V2, evidence, queue, reliability and intake checks passed after the changes. All 17 established and new local suites passed. Full CI status is recorded in the delivery message after publication.
