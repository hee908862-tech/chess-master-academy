# Authorized regression repair

The user approved addressing the remaining release-blocking failures on 2026-10-25, with records and scoring preserved and no removal of failing tests to obtain a green run.

## Product corrections

- Scoped active diagnoses now show their own progress in the home recommendation, preserving initial-course priority and all server scoring.
- Retained foundation lessons keep a clicked square's attack explanation instead of replacing it with a generic selection prompt. Independent/transfer lessons still conceal the explanation.
- Foundation completion places the next action before optional prose, preserves focus and board position without forcing viewport scrolling, and uses the available desktop board height.
- Cancelling an account switch clears both the original authentication request generation and the trial wrapper's UI lock. Late success/error cannot replace the newer account or copy guest progress.
- Narrow layout adjustments preserve readable boards, 44px controls, the full optional explanation, and accessible document scrolling. Active diagnosis keeps the position before the redundant resume card; timer semantics are unchanged.

## Test corrections and retained contracts

Current explicit disclosures and course selection replace clicks on hidden archived controls. Current saved-guest entry replaces the superseded login-required trial flow. These tests retain no-write return/replay checks, exact saved session/record comparisons, cancellation and delayed-response protection, keyboard focus, contrast, and actual hit testing.

Fixtures now include complete active-question payloads, wait for the actual ready/response boundary, account for same-owner GET coalescing, and load synthetic initial results through an explicit refresh. CP threshold tests explicitly select a non-mate objective so the separate exact mate proof does not bypass the mocked CP evaluator; expected outcomes and stored evidence assertions remain.

Generic browser servers load the real read-only blueprint before yielding. Preparation-failure tests continue to control their own responses. No new skip or xfail is added.

## Verification evidence before final CI

These are overlapping focused runs, not an additive total or a claim of a green full suite:

- Clip rules, API/UI, packaging and initial recommendation: 67 passed (`/tmp/residual-clips-regression.log`).
- Foundation UI, complete authored courses, square explanations: 14 passed (`/tmp/residual-foundations-final.log`).
- Retained-course navigation/history: 27 passed, then the corrected focus case passed (`/tmp/focused-paths-agent.log`, `/tmp/focused-paths-final.log`).
- State restore, CP evidence fixture and initial-result layout: 17 passed; final result-layout pair also passed (`/tmp/residual-protocols-agent-final.log`, `/tmp/residual-initial-layout-agent-final.log`).
- First visit/current account switching: 18 passed; related academy upgrade: 6 passed (`/tmp/first-visit-agent-final.log`).
- Guest/account security, reset and movement return integration: 13 passed (`/tmp/expanded-security-integration.log`).
- CI9 timing cases: 4 passed (`/tmp/residual-new-ci9.log`).
- Real diagnosis, five recommended tasks, fresh re-diagnosis and visual replay: 7 passed (`/tmp/residual-diagnosis-visual-final.log`).
- Midwidth layout, contrast and historical read-only guards: 10 passed (`/tmp/layout-checks-final.log`). Desktop diagnosis plus contrast: 4 passed (`/tmp/layout-diagnosis-contrast.log`); these overlap.
- Review account ownership and late analysis: 3 passed (`/tmp/residual-review-second.log`).

The full suite is collected on every CI worker and partitioned by file into four disjoint groups. Root static assertions execute during collection. Collection validation assigned all 1,280 cases across 141 files exactly once. Browser modules are interleaved separately from unit modules to avoid alphabetical clustering; a failing group does not cancel the others. Every group on the final head must pass before merge.

## Integration correction

CI10 on e20ebbc caught two board-position regressions from the completion scroll. The forced scroll was removed; mobile action order now makes the next action reachable without moving the board. All existing stability assertions remain. A parent review also found that the result-count test was inspecting the hidden active-course compact text; it now requires the actual visible result summary and progress element to show 8/48 before and after reload, alongside unchanged API preservation assertions. The combined foundation feedback/layout/visible result regression passed all 27 cases (`/tmp/ci10-foundation-fix.log`). CI10 also exposed two remaining test contracts: promotion cancellation intentionally keeps the source selected, and a training-view choice must wait for the authoritative dashboard response. Their corrected tests retain board/bookmark/account preservation and cover all four viewports (1 + 4 passed; `/tmp/ci10-study-cancel-final.log`, `/tmp/ci10-followup-fix.log`). A new exact-head full CI is required after these changes.

## Environment and release limits

The original attachments were inspected by the parent, not in this execution environment: supported Library materialization failed and was not bypassed. Parent compared the committed three priority screenshots to the originals. Local Chromium viewports are not physical Kakao/iOS devices.

Local Stockfish is unavailable; engine assertions remain enabled in CI with Stockfish installed. Docker COPY/import smoke passed. An actual local Docker build failed at Debian package retrieval because deb.debian.org could not resolve; no network/security workaround was attempted. Runtime build/deployment is not claimed complete until the existing main autodeploy confirms the merged commit.
