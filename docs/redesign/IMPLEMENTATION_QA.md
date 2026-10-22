# Academy redesign — implementation checkpoint, not production approval

## Baseline and preservation
- Current main and Render Live both verified at `2c457533e226e8403b58c1c396b5f076977c064d` (PR35 merged). No old PR changes reapplied.
- Live deployment: `dep-dbcm0r3m8hqs73afk4o0`, finished 2026-10-22 10:04:04 KST.
- Existing production account, diagnosis, game and learning records were not altered. Operational inspection only selected/deselected a piece; no answer, skip, next or new game was submitted.
- Existing scores are not rewritten. New scoped sessions use diagnostic-blueprint-v1, retain the unchanged skill-index-v1 formula and partition growth by level, competency, topic, corpus and assessment version.

## Direct operational reproduction
At baseline, open the existing diagnosis, select black pawn b7, click b7 again. The second click leaves b7 selected (one reproduced sequence). No move is submitted. A before screenshot is supplied separately.
A newly opened browser tab shares the existing account. It is NOT a genuine anonymous-browser test. No logout/storage deletion was performed to manufacture one.

## Implemented, with verification boundaries
1. Anonymous browser identity: real existing grading/learning/game/diagnosis routes. A browser key resumes server-side records; acknowledged snapshots are also copied locally. Offline grading is not provided. UI explicitly distinguishes the browser key/copy from authoritative server records and warns about browser data removal, private-window closure and other devices.
2. Guest-to-account linking is additive. It exposes a separate resumable namespace, not an aggregate-score merge or overwrite of the account's current sessions. Duplicate linking is idempotent; another account cannot claim or resume linked records. Login credentials are not needed for guest creation.
3. Guest creation/activity limits are separate from grading. Engine admission limits remain intact. Limits are per process; proxy addressing and multi-worker deployment require review before release. No paid service or infrastructure settings changed.
4. Diagnosis/training/repertoire/education/study selection cancellation fixed; foundation friendly-piece switching fixed. Shared pointer drag uses the existing click controllers and pending ghost, and confirmed animation starts at drop location. Reduced motion remains respected. Full browser gesture/animation regression is still required, especially old legacy boards.
5. Foundation arrows narrowed, shortened before piece centres, translucent, at most two overlays; distinct line/label semantics remain. En-passant begins with the preceding position, animates d7–d5 on request, marks previous squares, then lets users skip to practice or replay. Demonstrations never call progress/grade APIs.
6. Diagnostic blueprint choices: balanced 24 (12 basic/12 applied), domain 8 (4/4), subskill 4 (2/2). Explicit topic whitelist and corpus availability; insufficient unseen balanced samples return an error without replacing a session. Domain/subskill results never create an overall total. Partial diagnosis means a defined topic, not early exit. Measured scope excludes strategy/general endgame ability.
7. Result bars expose observation and unresolved counts directly. Unmeasured areas have no zero-length score bar. Scoped training and new scoped diagnosis are linked without modifying the prior balanced training cycle.
8. Game serializer supplies authoritative mate/stalemate and hypothetical king-escape explanations. UI prioritizes checkmate and win/loss, exposes the existing explanation toggle, and disables ended-game board input. AI level copy does not invent an Elo mapping.
9. Board/action layout remains in normal flow; responsive limits and expandable scope controls added. CSS/visual behavior is unverified in a renderer.

## Local verification actually run
36 tests passed, one Starlette/httpx deprecation warning, 26.00 seconds:
- test_redesign_contracts.py (5): real SQLite/API identity isolation, same guest progress after a new session, safe account linking/duplicate linking/ownership denial, shared feature endpoints, game restoration; fixed scoped corpus composition and full scoped result; topic validation; exact original promotion mate rules.
- test_redesign_selection.py (1): Node controller-only repeat click cancellation and friendly switching, NOT browser UI.
- test_journey.py, test_growth_cycle.py, test_board_presentation.py, test_foundations.py, test_engine_cleanup_observability.py, test_static_revalidation.py: existing functional/rules/CAS/engine-double regression.
- Modified JavaScript syntax checks and git diff --check pass.
- An initial test-harness extraction failed for the multiline education function; the extractor was corrected and the test passed. This was not an application regression.

A source wiring audit also found the legacy first-visit stylesheet hides every unlisted home child. The new full guest entry is explicitly exempted; without that override its implementation would be invisible to actual guests. This fix still requires browser verification.

## Not verified / not complete
- Modified code has not been deployed or operated in a browser. No after screenshot, UI pass or production pass is claimed.
- No independently isolated anonymous browser context was available; a new tab shared the existing account.
- Current cloud browser has no viewport resize capability. Requested 1366×768, 1180×650, 390×844, 360×800, landscape and zoom checks are pending; no physical mobile tested.
- Actual Stockfish binary is unavailable locally. Prior installation permission failure was not retried or bypassed. Engine doubles and python-chess rules checks are not actual engine validation.
- Pointer animation, promotion cancellation, slow/reordered frontend responses, all legacy screen wiring and account-switch interactions need browser regression before merge.
- Browser snapshots do not provide offline play; server connectivity is required for authoritative grading and saves.
- Guest data is stored on the existing server; this is not browser-only or a promise of permanent storage. No data deletion/retention automation added.
- Subskill availability counts are preliminary: overlapping/previously seen positions may cause start to refuse despite sufficient raw pool counts; refusing is safer than substituting a different skill.

## Release gate / next checks
Use a browser-capable local/staging environment with an approved Stockfish executable. Run isolated guest -> all five functions -> reload -> account link -> second-device resume, preserving both account and guest active sessions. Then test the pointer and promotion matrix across all boards and screen sizes, en-passant replay without progress duplication, scoped reports/training, and mate/stalemate. Only after these checks should this draft be merged; use the existing Render auto-deploy and verify the actual Live commit and flows. No manual deploy was triggered.

## PR #36 follow-up: linked-record authorization and observed recommendations (2026-10-22)

Baseline checked: main/Render Live `2c457533e226e8403b58c1c396b5f076977c064d`, PR head `46cc7e49682d74554580919091c1d896b6868ab5`.

- A linked guest namespace now rejects every standalone guest bearer, including keys issued before this patch. Only a delegated key bound to a live session of its owning account is accepted. Owner logout or 30-day account-session expiry invalidates that delegation on the server. Unlinked guest keys retain browser restoration; their lifetime is not shortened. No record copy/delete/score migration occurs.
- Linking stays idempotent for the owner; the former anonymous key can prove a repeat link request but cannot authorize record reads/writes. Other owners cannot claim/resume it. The UI separates linked resume keys from anonymous keys, clears the anonymous cache after linking, and reacts to cross-tab key removal. Existing account sessions now have a 30-day authentication lifetime; expiration does not delete progress.
- Scoped recommendations rank confirmed error, confirmed partial reference execution, then helped success. Unanswered/unverified/equivalent-but-unfinished observations do not become weaknesses. Sparse observations request more diagnosis; confirmed successes offer maintenance. Exact skill tags and original-position exclusion are enforced for new candidates. Missing candidates return 409 without an unrelated substitute; original tasks are explicitly offered as review. Scoped completion is idempotent and does not credit the balanced five-task cycle. Existing score versions are unchanged.
- Render get_service: Docker, one Free instance, automatic deploy on main commit. Docker command has no explicit multi-worker option; current startup log contains one `Started server process [1]` at 2026-10-22 01:03:56 UTC. No forwarded IP header is trusted. Per-process counters were replaced by atomic database counters: global creation 300/hour, namespace activity 180/minute, owner link/resume 30/minute each. 429 returns Retry-After and a retry message. Creation is a shared capacity cap, not a per-person abuse detector: a determined actor can exhaust it. No infrastructure/permission/paid-service changes. Shared PostgreSQL deployment behavior is not locally integration-tested; SQLite concurrent callers are tested. Future isolated SQLite replicas would require a shared store before scaling.
- Fixed a deployment blocker: Docker now copies `guest_access.py` and `diagnostic_blueprint.py`.

Validation distinctions: real SQLite/API tests and Node controller checks are local, not operating-browser tests. No real Stockfish was available in this environment; engine-boundary tests do not claim real-engine validation. The available browser shares the existing signed-in account, with no isolated context or viewport control; do not destroy that session to fabricate guest/mobile coverage. Physical mobile, isolated operating link/logout/recommendation flow, motion and responsive layout remain manual checks. Repeated blocked engine/browser installation was not attempted.

Follow-up local results: regression selection 65 passed / 4 skipped (real Stockfish unavailable), plus 1 Node guest identity/logout/storage-event test passed. Python compilation, changed JavaScript syntax checks and `git diff --check` passed. SQLite tests exercise pre-link reload, repeat linking, old-key reads/writes denied, second-client denial, owner logout, expiry, other-owner rejection, fresh owner login/device resume, unchanged record contents, and atomic concurrent budgets. Scoped tests cover late-only errors, all-success, uncertainty, help, multiple weaknesses, exact-tag novel candidates, absent candidates and duplicate completion. These are not physical devices or actual browser end-to-end results.

## Post-merge isolated browser and real-engine follow-up

See [FOLLOWUP_QA.md](FOLLOWUP_QA.md) for the PR36-baseline reproduction, three UI corrections, 106 local passes, real-Stockfish timings, and explicit operating-network limitations. Earlier pending checks above are historical, not claims of current operational success.

## PR38-baseline whole-app clarity follow-up

See [whole-app survey and QA](../qa-whole-app/README.md) for the screen-by-screen information hierarchy, two real local learning flows, historical-text preservation, initial-load investigation, responsive/keyboard checks and deployment verification. Earlier operating/browser limitations above remain historical; local Chromium and real Stockfish checks must not be confused with operating UI or physical-device validation.

## PR40-baseline visual teaching and evidence follow-up

See [visual teaching / diagnostic evidence QA](../qa-visual-evidence/README.md) for legal attack/protection diagrams, automatic en-passant, separated diagnostic scopes, read-only replay analysis, versioned cumulative evidence and radar comparisons. Prior scores and active sessions remain unchanged; newly exposed broad diagnostic areas use a new measurement condition. Original attached pixels are unavailable in this execution environment; the parent operator will independently compare them after deployment.
