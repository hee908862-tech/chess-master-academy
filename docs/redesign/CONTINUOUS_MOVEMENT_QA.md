# Interactive basics curriculum

## Scope and research

The new `interactive-basics-v1` contains 62 original scenes across 18 topics: 17 movement sandbox scenes and 45 rule scenes, separate from diagnostic scoring. It teaches rook, bishop, queen, knight, king and pawn through short rules, target collection, and a final unmarked application scene per piece. In movement scenes, target-free legal detours are accepted. Consecutive moves use the same learner piece; these are not alternating turns in a real chess game. Initial king movement scenes have no enemy attacks; subsequent rule scenes use full legality for checks, promotion, castling and en passant. The original foundation lessons also remain available with their old progress.

Official Lichess sources inspected: [rook stage](https://raw.githubusercontent.com/lichess-org/lila/master/ui/learn/src/stage/rook.ts) and [level controller](https://raw.githubusercontent.com/lichess-org/lila/master/ui/learn/src/levelCtrl.ts). They show target collection, learner-side turn restoration, destination reselection and automatic transitions. The parent browser separately observed these interactions on the official desktop Learn UI, including legal non-target knight moves. Our web fetch of `/learn` returned an assets/network warning, so it was not a direct UI operation here. No external code, artwork, logo or lesson wording is copied. Personal feedback screenshots were not stored in the repository and were not opened in this implementation environment.

## Data and rules

- Additive `movement_v1` progress only; original `foundation_v1`, `rook-first-v1`, diagnostic sessions, scores, timers and games remain unchanged.
- Existing foundation users retain their original route unless explicitly selecting the new movement course. New users get the new course by default. Most recently used version determines the preferred resume route.
- The server replays cumulative move/selection/placement actions from its authored initial position, restricted to the learner piece. No null moves, king captures, promotion, en passant or castling in the movement sandbox. Rule scenes use full legal chess moves, including special rights and promotion choices; setup placement is explicitly separate. These incomplete game positions are not sent to analysis engines.
- An opaque run ID, content/policy version and revision identify the checkpoint. Exact snapshot retries are idempotent; divergent or shortened paths conflict rather than overwrite. State writes retain existing account auth and transactional compare-and-swap.
- Explicit restart archives the previous run. Historical completion remains counted; an active new run is separately incomplete. Guided target completion, first unmarked application, and repeated/helped application are distinct observations, not certified mastery or rating changes.
- A 128-move per-run bound prevents unbounded checkpoint payloads. Reaching it is not completion. A pawn can legally choose a path that leaves targets behind; the UI must explain that pawns cannot return and offer an explicit restart, preserving that run.

## Verification status

Server/content and preservation tests added in `tests/test_movement.py`. Existing foundation, PR48 understanding, PR47 scoring integration, and Docker COPY/import checks are included in regression validation. Browser validation and final totals are recorded after integration below.

No actual learner or TEST3 records are changed by these tests. Synthetic accounts use disposable local SQLite databases. No physical mobile device or follow-up novice study is performed. Stockfish is unavailable in this resumed environment; the previous official download attempt returned `Tunnel connection failed: 403 Forbidden`, and is not retried or bypassed. New movement rules require python-chess, not Stockfish. Operational UI validation remains separate from local emulation and deployment status.

## Expanded scope and licensing decision

The later request expands this work to all 18 stages listed by the official [stage registry](https://raw.githubusercontent.com/lichess-org/lila/master/ui/learn/src/stage/list.ts), not only six movement types. Advanced scenes require distinct success conditions; educational pauses for stalemate and scripted opposing moves for en passant must remain where needed. The complete correspondence, source stage counts (110 original exercises), and intentional differences are tracked in [BASIC_CURRICULUM_MAP.md](BASIC_CURRICULUM_MAP.md).

The official [copying rules](https://raw.githubusercontent.com/lichess-org/lila/master/COPYING.md) apply AGPL-3.0-or-later by default to stage code/data; Learn piece art has a GPLv2+ exception, the star SVG CC0, and the logo is restricted to referring to lichess.org. This implementation does **not** import their stage data, translations, code or assets. It uses independently authored positions, predicates, Korean wording, the application's existing pieces and its already-vendored chess.js. No new Lichess-derived redistribution obligations are introduced. The shared educational objectives and interaction patterns are the reference, not copied lesson content.

## Final local verification (2026-10-23)

- Server/content, additive progress preservation, old foundations, PR48 understanding, PR47 saved score integration and image packaging: **108 passed**.
- Existing foundation feedback, old beginner flows, branch exploration and common move sound browser regression: **45 passed**.
- Home/profile resume and explicit return to the legacy course: **2 passed**.
- Guest account linking, logout, refresh/other-tab protection and owner re-login: **3 passed**.
- New curriculum browser suite: **15 passed** (275.55 seconds), including all 45 rule scenes on PC and mobile viewport, Python/JavaScript rule parity, consecutive sandbox moves, draft recovery, accessibility and audio. A final empty-string draft recovery fix also passed the same focused test separately; this rerun is not counted twice.

**173 distinct tests passed** across the groups above. The initial dense full-scene timeout was traced to the unchanged request limit; the final paced run passed. No unresolved test failure is reported as a pass.

Browser tests use local Chromium with disposable synthetic identities. Viewports include 1366×768, 360×800, 390×844 and 844×390; CSS 200% zoom, keyboard/list input, reduced motion and mute are tested separately from real devices. Injected 800ms save latency allows consecutive moves while the save is pending; selection stays on the moved piece, the newest local position is retained, and the asserted board vertical displacement is below 1px. This is a local test condition, not a production latency claim.

Independent review caught and corrected invalid temporary-draft recovery, failed preparation moves reverting the displayed position, and a help-opening race during automatic transition. A dense full-curriculum browser run reached the existing guest 180-request/60-second limit; this is not disabled. The recovery test waits for the advertised interval and explicitly retries the preserved checkpoint.

## Operational handoff

Open `#learn/movement` in a separate identity. Before identity creation it offers an explicit login-free start; merely visiting does not create an account. Check two consecutive rook moves without reselecting, a legal non-target detour, and a blocked move; then use “도움말 · 다른 과정 · 저장 상태” to choose special-rule scenes. Check promotion choice, the actual opposing en-passant move, and manual continuation after stalemate. Home/profile must resume the saved scene. Legacy progress remains selectable from the existing basics list. Do not write to the shared TEST3 browser for this check.

Deployment Live status is separate from operational interaction validation. No production learner writes, physical mobile tests, actual novice follow-up, or real Stockfish regression are claimed. The curriculum covers the mapped objectives in 62 original scenes; it does not claim the original 110 exercises’ repetition, difficulty or learning efficacy.
