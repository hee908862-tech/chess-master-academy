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
