# PR34 follow-up (in progress, not a completion report)

Baseline main and Render Live both verified as 2c20b850af48232d2521f82021d1955552324592.

## Corrected evidence classification
- 2026-10-21 22:49:00 UTC: diagnosis item 1 only shows engine analysis failure / judgment deferred. The original captured DOM does NOT prove TimeoutError.
- 2026-10-21 22:52:17 UTC: item 19 includes engine_failure / TimeoutError / unverified.
- These failures must not be assigned a common root cause without evidence.

## Corpus recovery
Each original board was matched by exact piece placement plus the preceding opponent move and expected continuation, not by question ordinal alone.

|Case|Puzzle ID|Corpus FEN|Analysis FEN|Submitted move|
|---|---|---|---|---|
|1|bhYwD|2Q5/6pk/4p3/5p2/1P1PpP2/4P3/2R2KPp/3q4 w - - 0 47|2Q5/6pk/4p3/5p2/1P1PpP2/4P3/5KPp/2Rq4 b - - 1 47|d1d2|
|19|EM5dO|8/B6R/1P1p4/3k4/P7/6Pp/5rr1/4R1K1 w - - 2 40|8/B6R/1P1p4/3k4/P7/6Pp/5rr1/4R2K b - - 3 40|f2f1|

Canonical preceding moves: c2c1 and g1h1 respectively. Expected continuations: h2h1n; g2h2 h1g1 f2g2 g1f1 h2h1.
Case 19 captured settings: Threads=1, Hash=16 MB, 0.3 seconds/position, max depth 16, minimum depth 10. Same settings exist in baseline code; case 1's original detailed settings were not captured.

## Changes prepared
- Explicit engine transport close even when quit fails, with admission release once. An analysis exception is preserved when shutdown also fails.
- Queue, startup, configure, before/after analysis, shutdown and total durations. No engine search budget, depth threshold, score version or grading threshold change.
- Guest opening layout groups board/status/playback together; desktop explanation column, mobile normal-flow stacking, collapsible scope. No fixed overlays or removed explanations.
- HTML and static files revalidate on subsequent requests with Cache-Control: no-cache. No forced reload, storage clear or session mutation.

## Validation completed
22 tests pass: test_static_revalidation, test_engine_cleanup_observability, test_growth_cycle, test_journey. Controlled tests include normal analysis, timeout, engine termination, startup failure, concurrent admission, and existing API revision/duplicate-submit checks. These are NOT a real Stockfish proof.
node --check public/guest-practice.js and git diff --check pass.

## Blockers / pending
- Real Stockfish unavailable locally. apt-get update fails with setgroups/seteuid Operation not permitted. No permission or network workaround attempted. The included scripts/reproduce_operational_alternatives.py requires a real explicit --engine path and refuses to substitute a fake.
- No claim that either production engine failure has been fixed. No production timing data yet. API response latency still needs operational measurement.
- New-account full valid diagnosis, 5/5 training, repeat completion and re-diagnosis remain pending authentication and actual UI execution. Existing accounts/records have not been changed.
- Viewport control unavailable in current cloud browser. Requested dimensions, zoom, mobile/landscape and physical devices are unverified. Previous Chromium download network restriction remains unresolved.
- AI game rules/statistics, R2 remainder and R4 legacy UI support need operational checks. README_DIAGNOSTIC_JOURNEY says legacy 49-question flow remains accessible; do not mark it retired without current UI evidence.

## R3 rules-only verification
Original requested FEN: 6k1/3P1pp1/p6p/8/1p6/1P1Q3P/P5PK/2qq4 w - - 0 1.
python-chess verifies valid position; d7d8q SAN d8=Q# and d7d8r SAN d8=R#, both legal, checkmate, zero legal replies. Operational puzzle grading is still unverified. No production puzzle changes made.

A further controlled regression covers shutdown failure after evaluation: partial loss_cp is discarded and journey grading now requires explicit verified_error status. This prevents failed analysis lifecycle evidence from being used as a scored error. This is a confirmed local failure path, not proof of the historical production root cause.
