# Read-only branch exploration and bounded evaluation

## Product contract

`cmaExplore.offer(boardId, fullFEN, {flip, allowed})` mounts an explicit details panel adjacent to the original board. `null` removes it. The separate board uses chess.js 1.4.0 for local legal moves, promotion, castling, en passant, undo and return to the original full FEN. Original source objects, submission APIs and scores are never changed by branch play. Source/identity/navigation changes cancel stale analysis and dispose or close the branch. Evaluation and white-perspective meter sit immediately after the board; technical details are expandable.

Analysis is only an explicit button request. It uses the existing authenticated `/api/study/position` with `evaluate:true`, not a new public endpoint. There is one shared engine admission, account cooldown 10s and process-wide 2s, 128-position evaluation cache, 512-account rate cache. Search is capped at 0.2s/depth14/60000 nodes, engine protocol timeout3s, client12s cancellation; these are configured limits, not measured response promises. Cached results remain labeled engine/depth/white POV. Mate, terminal rules, unknown, failure and zero/draw are distinct. Best move is **current side's limited-search recommendation**, not a guaranteed optimum or always an opponent move. Before/after delta appears only when both positions have cp evidence. No automatic server call follows a move.

`engine:false,evaluate:false` remains the prior legal read-only study API. Evaluation authentication happens before cache lookup. No assessment source access, ownership relaxation, identity auto-generation, score or learning writes are introduced. Learning practice allows the panel before completion only after the existing answer-reveal action has been saved (`analysis_help_recorded` from server); verification remains locked until completion.

## Board coverage / gates

| Board | Exposure rule |
|---|---|
| diagnosticReplay* | Confirmed submitted/historical replay frames only; original evaluation button preserved |
| journeyBoard | No direct analysis during question; confirmed feedback uses replay component |
| initial-source-* | Result representative sources only |
| testBoard legacy V8 | Confirmed feedback answer FEN only; new unanswered question and evaluation game remove panel |
| v8MateBoard | Finished only |
| learningBoard | Done or read-only concept; practice after recorded answer reveal; unresolved verification hidden |
| reviewBoard | Saved game selected frame; identity reset removes |
| studyReviewBoard/studyOpeningBoard | Existing free read-only exploration full FEN |
| openingBoard | Legacy teaching mode, no independent first-try scoring |
| educationBoard/repertoireBoard | Confirmed answered or finished only |
| foundationBoard | Solved or read-only en-passant demonstration only |
| guidedBoard | V4 finished, V5/V6 confirmed completed step; next unsubmitted step clears |
| v9PuzzleBoard/v9CourseBoard | Confirmed saved/completed result only; new/current unanswered clears |
| challengeBoard/challengeReviewBoard* | Confirmed feedback/end or historical frames only |
| guestBoard | Completed example only |
| ruleBoard | Intro teaching explicitly no first-try penalty; full FEN only, invalid kingless positions refuse rather than invent rules |
| legacy puzzleBoard | Solved or confirmed submitted practice result; new question clears |
| gameBoard | Excluded live AI game, including cached-board redraws |
| homeBoard | Decorative preview, no activity/assessment; no analysis control |
| trialBoard | Kingless rook toy uses pieces rather than a valid full FEN; no fabricated turn/castling state or engine score |

All branches refuse malformed full FEN. Toy positions without both kings cannot be treated as legal games. No claim that decorative/invalid toy boards have a meaningful engine score.

## Distribution and limitation

Local chess.js ESM 1.4.0 and BSD-2-Clause license are vendored from the publisher npm package, SHA512 checked against registry metadata. No runtime CDN. Sources: https://github.com/jhlywa/chess.js/tree/v1.4.0 ; https://registry.npmjs.org/chess.js/1.4.0 .

Browser Stockfish was investigated via publisher https://github.com/nmrugg/stockfish.js and official npm stockfish18.0.5. The npm package integrity was verified, but contains compiled artifacts and license/README, not corresponding source. A CDN request and exact GitHub source archive request separately returned HTTP403. Neither blocked endpoint was retried nor proxy/tunneled. **No browser Stockfish binary is shipped.** Existing server Stockfish is the bounded manual fallback. This is a limitation, not a claim of completed browser-worker deployment.

## Validation

`tests/test_branch_evaluation.py` + existing study suite: **21 passed** (2026-10-23, isolated local SQLite). Includes real Stockfish original example black advantage/white POV/legal recommendation; doubles check explicit limits, rate/cache, unauthorized token, invalid FEN, engine missing is failure not zero, terminal mate/stalemate without engine, original account state unchanged. A first fixture failed because a prior cached position correctly remained available when the engine path was disabled; failure fixture changed to an uncached FEN and independent rate time. No production records used.

Parent integration tests cover real Chromium local branch moves/undo/replay and responsive layout separately. They are not real mobile-device or novice-user observation. The regression FEN is screenshot-derived, not an identified TEST3 source item: `8/2k5/1Np2K2/P1P2ppp/1P6/3b2P1/7P/8 b - - 0 1`; local `f5f4 g3f4` stays legal, original source remains unchanged.

Follow-up contamination guard: opening/moving/undoing a branch queues full positions to the separately authorized `/study/exposure` record, at 500ms batching up to 32/request. This changes only separate help/exposure history, not original answers or scores. Moves never await this write. Failure/overflow are explicit and retry is user-controlled. Identity changes stop sending the prior identity's pending batch and preserve its durable queue for the original identity; anonymous branches show that server exposure is untracked and are not silently attached to a later account. Root owns endpoint/persistent eligibility integration and tests. The preceding “no writes” description applies to grading/original state and evaluation endpoint, not this separate exposure ledger.

Durable pending ledger correction: pending positions now persist in browser localStorage under SHA-256 namespaces, preferring the confirmed `/me` account code (`summaryOwner` must match the current token), with a token-SHA fallback until confirmation. No raw credential is stored by this ledger. Verified account scope merges the fallback into the stable scope so same-account relogin can recover pending history. A different identity never inherits or flushes the prior owner's pending list. `flushExposures()` loads the current persisted ledger even if no branch is open, awaits saves before independent start/submission, and returns false on network/storage/overflow/invalid-ledger failure. Pending capacity is 512 FENs; overflow is explicit and blocks measured starts rather than dropping evidence silently. Storage write failure leaves local moves usable but prevents measured starts. This supersedes the earlier memory-only limitation.

Durable-ledger regression: `test_branch_pending_browser.py` (3) plus existing branch matrix (9) **12 passed in 40.78s** on local Chromium. Cases: failed save→reload without reopening branch→guard still false→retry succeeds; different identity never sends prior pending FENs→returning owner restores pending; localStorage quota failure blocks measured start while legal moves work→storage recovery permits retry. This is local browser testing, not operating account migration or real mobile hardware. A fixture-only first run failed because Playwright evaluated the assigned mock function as its return value; wrapping the fixture assignment corrected it, then all cases passed.

Further identity-race and storage checks: the final pending-ledger suite adds rotated-token-before-cached-`/me` recovery, no pending history with `/me`503 (no additional account read required), and real pending history with unknown identity plus `/me`503 (measured start blocked). Namespace scans are restricted to this feature and bounded at 128 keys. Confirmed account identity is reused; an explicit bounded `/me` read is needed only when pending ownership is genuinely unresolved. Successfully delivered, empty temporary queue keys are removed; this does not delete any account, original score or server exposure history. On verified migration the stable owner queue is written before removing that owner's fallback queue. Failed/nonempty/prior-owner pending data is preserved.

Final pre-merge safety correction: a nonempty token-scoped queue without confirmed account provenance is never silently ignored after token rotation, even when the replacement identity's `/me` succeeds. Independent attempts remain on hold with an explicit instruction to return to the original login/guest identity; the queue is not assigned to another account. Account-scoped queues remain separate. Temporary successfully delivered queues are removed, not account or historical server records.

Scoped `requireExposureSaved()` preflights now cover learning verification/start/path/retention/cycle and scored moves, challenge start/move/next, V9 puzzle/course start/next/moves, legacy puzzle/practice submissions and retries, and V8 assessment/mate starts and answers. They do not wrap every API or recurse into exposure writes. Failure means no scoring request and no charged wrong attempt. The shared preflight captures identity, route and board navigation version; task-specific paths also recheck generation/task snapshots after waiting, before issuing a request or applying an optimistic move.

Final durable-queue/guard regression result: `tests/test_branch_pending_browser.py` **11 passed in 24.10 s** (isolated local Chromium, 2026-10-23; `/tmp/branch-finalguard2.log`). Includes failed write→reload→retry, same-owner rotated credential recovery, different-owner isolation, storage failure while legal moves remain usable, no exposure/no extra `/me` dependency, unresolved identity failure, unbound old identity after successful replacement `/me`, failed exposure→training/puzzle/challenge issuing no start request, and delayed successful exposure response after navigation cancelling preflight. Syntax checks and `git diff --check` passed. Operating account writes, real mobile hardware and human novice observation were not performed by this suite.
