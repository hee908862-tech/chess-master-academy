# Academy upgrade validation and compatibility

Base: main PR31, `395d492d136fbd3aa5eb392d85223884ee01b465`.

## Internal diagnostic index

`skill_index.py` defines `skill-index-v1`, fixed six-domain blueprint. Each domain
uses 40% basic [600,1200) and 60% application [1200,1800) task performance.
These are authored weights and external task difficulty bands, not calibrated
IRT parameters. Each complete linked line is one item. The domain fraction is
`0.4 * basic_success_fraction + 0.6 * application_success_fraction`; six domains
have equal weights. Display uses `1 + floor(2999 * fraction + 0.5)`.

Examples: basic-only success = 1201; application-only success = 1800;
all verified failures = 1; all complete = 3000. This changes the construct to
whole-line completion with application weighting, rather than multiplying the
old partial-ply score. Unknown alternatives, partial execution, hints, repeated
positions and missing observations do not become failures. They produce bounds
and suppress the point estimate. Every assigned item must be adjudicated and
both bands present. Deduplication covers puzzle IDs and overlapping positions.

The index is provisional. The sample reference range is conditional on sampling
assumptions, not a calibrated ability confidence interval. A one-point difference
does not establish precision. Strategy and general endgame skill remain unmeasured.
Later validation needs item-response data, coverage/selection-bias audits,
reliability checks and a versioned linking study before cross-version comparisons.

New balanced/quick sessions pin the new version at start. Existing active sessions
without that marker finish on `growth-v1`; old reports are never recomputed.
Graph series separate score, assessment, competency, corpus and mode versions.
No XP, accuracy, game rating, or external difficulty formula/storage is changed.
No database schema migration or backfill is required. Education accepts the
previous published version only when its saved lesson is identical to the retained
lesson, preserving in-flight work while still blocking unknown stale content.

## Other changes

- `diagnostic_replay.py` and GET journey replay derive frames from saved full FEN
  and legal UCI lines; initial turn, castling, en passant and clocks are preserved.
  Shared UI starts before the answer; controls never grade or write. Missing or
  corrupt snapshots fail closed. History retrieval checks account ownership.
- Classic/royal pieces share exactly the same per-kind SVG geometry for both
  colors. Chessnut Apache-2.0 source, copyright and modification attribution ship
  under `public/assets/pieces/chessnut-source`. Legacy Unicode preference uses SVG.
- Four original mini-lessons: supported rook mate, pawn-race calculation,
  rook-pawn corner stalemate, 50/75-move rules. Each includes concept, practice,
  common mistake, reason and a changed position. Rule outcomes and legal moves
  are checked with python-chess; no unsupported general tablebase-win claim.
- First guest screen exposes bishop, knight, mate and opening previews directly;
  rook completion links to them. Opening preview explains center, development
  and king safety. Full opening exploration remains available.
- Logged-in account inputs are hidden until explicit account switching. Cancel
  preserves the current token and clears PIN input. Guest work is not credited
  automatically; no new analytics or tracking dependencies.

## Verification scope

Local tests use disposable SQLite databases. Browser coverage includes 1180x757
and 390x844, anonymous discovery, no-write previews, replay exact FEN, account
switch cancellation and score rendering. `test_academy_upgrade.py` covers legacy
session/report preservation, ownership, duplicate evidence, score bounds, legal
replay and education. `test_image_runtime_package.py` stages actual Docker COPY
payload, generates the journey index and imports the server in isolation.

Final command outcomes are recorded in `verification.json`. Screenshots are local
QA, not claims about authenticated production state. Live checks after deployment
are read-only health and static asset checks; no production learner records are
created or replayed for QA.
