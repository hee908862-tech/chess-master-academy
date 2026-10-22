# PR36 remaining verification — 2026-10-22

Baseline main and Render Live: `e99e8091d738fc2de8ee85e534f2c77f38925495`. No open PRs and a clean worktree at start. No AGENTS.md or applicable .agents skill was present. Earlier checkpoint claims in IMPLEMENTATION_QA.md are historical; this report adds evidence without treating those pending checks as passed.

## Reproduced UI defects and fixes

- Full guest entry was hidden. The earlier redesign.css override lost to the more specific first-visit.css selector containing multiple :not IDs. Exclude #guestAccess directly from that hide rule.
- Guest linking controls were swept into the growth/statistics panel by info-layout installation. Keep them in the account panel; browser linking and owner resume are now accessible there.
- En-passant demonstration read `demonstrationnstration` instead of `demonstration`. Browser reproduction showed the next-demo button hidden and the practice position replacing the pre-move demonstration. Correct the property lookup. No save/grading/session schema changes.

## Local passed: 106 tests

- 34 engine/API/controller cases: test_learning.py (including all four formerly skipped real-Stockfish cases), guest link security, redesign contracts, guest browser state, engine cleanup observability. No skips.
- 54 existing motion, interaction/premove, scoped recommendation and selection cases. Controlled-response browser cases are not actual grading evidence.
- 15 new Chromium cases: three viewport sizes (1366×768, 360×800, 390×844) for guest/link/logout/reload/cross-tab denial/owner login and resume, read-only en-passant demonstration and selection cancellation, drag/promotion cancellation/delayed acknowledgement, scoped unanswered-result reasons and horizontal button fit, and actual active-diagnosis repeat-selection cancellation. Guest and diagnosis cases use real local API/SQLite; promotion delay uses intercepted responses. Linked and owner foundation snapshots remain distinct and unchanged. Old guest/delegated keys return 401 after linking/logout; no credential values are recorded.
- 3 existing account/settings panel state-preservation cases (320, 390, 1280 widths).

All browser accounts and databases were disposable and local. Mobile sizes are Chromium emulation, not physical devices/touch-hardware certification. The screenshot captures the actual 390px pre-move demonstration. Selection/display-only checks assert no POSTs and unchanged saved state. UI tests do not exhaust every legacy board or every reordered response combination.

The initial real-engine import test assumed the same candidate count on every time-limited analysis. A second search found an additional qualifying ply with a different deterministic ID; no duplicate position or overwritten card was observed. Corrected the assertion to preserve each prior card exactly and allow at most one card per eligible ply. Production import logic is unchanged.

## Alternative-move TimeoutError investigation

Official Stockfish 17.1 Linux x86-64 AVX2 binary ran locally. scripts/reproduce_operational_alternatives.py was run against both supplied corpus cases. bhYwD/d1d2 took 220ms; EM5dO/f2f1 took 237ms. Both reached depth 16 and returned unverified/mate_requires_proof, not a timeout or certified equivalent move. Detailed stage timings are in alternative-evidence.json. Startup was ~207/209ms. No production load test was performed.

TimeoutError was not reproduced, so the historical operational cause is **undetermined**, not fixed or disproved. Controlled startup/analysis/shutdown timeout and slot-release tests pass; these verify error handling, not the historical production cause. Future diagnosis needs failure-stage/timing evidence from the actual failed request rather than guessed CPU/network causes.

## Packaging and operational boundaries

JavaScript syntax, whitespace checks, Docker COPY input existence, and build_journey_index.py passed (40,713 unique items). The changed assets are under Docker's COPY public directory. No Docker configuration or paid/security setting changed. Render's actual image build and Live revision are checked separately after merge.

Production /api/health was attempted once from this newly provided environment. It failed before reaching the app: curl exit 56, CONNECT tunnel failed, response 403, HTTP 000. No retry, alternate proxy/host, shared-browser logout, or existing QA-account access. Consequently production guest/link/logout/mobile/scored-diagnosis flows remain **unverified**; management-API Live status is not interactive proof. No production records were initialized, reset, copied, or overwritten.

Remaining external checks require an authorized network/browser environment that can access the operating site, using a separate test identity; physical device gestures remain manual. No user credential or security-setting change is requested by this patch.
