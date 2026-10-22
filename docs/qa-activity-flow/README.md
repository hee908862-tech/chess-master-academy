# Seven usability follow-ups after PR37

Baseline: main/Render Live `9c272ad1f4841ea8bf1673aed1c27321178a2af8`; no open PRs, clean initial worktree. No AGENTS.md or applicable .agents skills found. The parent's PC 1180×757 operating observations were supplied evidence, not a new operational inspection by this executor.

## Seven implemented changes

1. **Home:** one saved-learning entry offers 기초부터 배우기 / 원하는 활동 고르기. Server/browser-key storage is explained once there. Unsaved demonstrations remain in a separate disclosure; their actions never award formal completion.
2. **Foundations:** explicit primary clicks start the recommended first/next course, resume an unfinished lesson/review, or show the completed user's review list. Free course selection remains separate. Duplicate clicks, identity changes, and navigation during a read cannot start a second/stale lesson. No auto-start on ordinary page load.
3. **Diagnosis:** one comparison presents the server catalog's 24/8/4 questions, time estimates, purpose and resulting scope. Beginner guidance goes to foundations. Prior introductory/quick/legacy controls and saved sessions/history remain reachable in a separate disclosure. Scoring, corpus choice, first-exposure rules, hidden answer lengths and scope comparison limits are unchanged.
4. **Training:** a board-adjacent brief distinguishes first-move-only (one move), full sequence (until authoritative completion; hidden answer length stays hidden), and situation practice conditions. Titles qualify the actual evaluation scope. Fresh/review/verification actions have purpose-based labels. Old paths, records and measurement notes remain available in details; empty saved-activity cards no longer dominate.
5. **Opening:** board and move explanation precede long guidance. Course/mode/orientation settings default closed with a current-course summary. Explanation-visible learning and unaided recall have separate buttons; all variations, reference search, direction and bookmark functions are preserved.
6. **Language:** authored foundation explanations say 세로줄(파일). A shared save-status formatter shortens confirmed/pending boilerplate while retaining verdicts, unknown outcomes and error detail. Unsaved trial handoff starts real foundations without crediting trial success.
7. **Return visit:** a shared recommendation model appears above home activity disclosures and in profile/results. Saved unfinished activities take priority; this browser's most recently visited active route is preferred and the selected activity/step is named. Other active activities remain selectable. The browser stores only a route preference scoped to the existing namespace code, not scores or access keys. Every recommendation requires current server reads. Read failures offer retry rather than inferring no progress. Scoped result recommendations reuse the server's task and reason; uncertain/unanswered observations do not become weaknesses. The same model is used on all three screens.

## Actual verification

128 unique tests passed, no skips: 29 core preservation/rules/growth/guest checks; 72 existing game input, motion, diagnosis, learning and profile regression cases (including four actual Stockfish tests); 6 isolated guest link/logout/cross-tab/re-login and en-passant browser cases; 19 new activity-flow cases; 2 actual opening branch/recall/bookmark/reference browser cases. One existing Starlette/httpx deprecation warning. Full per-suite counts are in test-summary.json.

Local browser matrix: 1366×768, short 1180×650, 360×800, 390×844, landscape 844×390. Tests assert no horizontal document overflow or clipped visible action-button text, and include 125% CSS zoom (not physical-device/browser-zoom certification). Tested direct first practice, actual a1–a4 answer, return/home/reload, complete and in-progress review routing, duplicate entry, late response after navigation, failed restore/retry, preserved training and diagnosis snapshots, diagnosis selection/resume, opening learning/recall, and shared scoped recommendation reasons. Unsaved trial success transfers no completion credit. Tests use disposable local SQLite and isolated Chromium accounts only. Actual local screenshots include desktop/mobile home, opening and training; desktop opening board and explanation are simultaneously visible.

Existing click/drag-related game interaction, promotion/premove and pending response suites passed. This is not exhaustive proof for every device, accessibility technology, latency ordering or legacy UI path. Natural page scrolling remains; no overflow clipping or reduced font sizes were introduced to manufacture a fit.

JavaScript syntax, git whitespace, Docker COPY inputs/static asset references and corpus-index generation passed. Docker includes the new files via COPY public. No dependencies, security permissions, deployment configuration or paid services added. No account, game, score or session migrations. Temporary generated index and unrelated existing screenshot outputs are excluded from this commit.

## Operational boundary and handoff

This executor's operating-site connection was previously blocked by the environment CONNECT proxy (`curl (56): CONNECT tunnel failed, response 403`, HTTP 000). It was not retried or bypassed in this task. No shared operating browser or existing operational user/QA identity was accessed. Live deployment receipt is verified through Render management after the merge, not treated as interactive operating QA.

The parent reported a separate authorized cloud browser that can reach production. After the new Live commit, recheck a new guest's primary foundation entry, the unified diagnosis choices, return-home recommendation and mobile opening/training; preserve old accounts and unfinished diagnoses. Physical devices, screen readers, real browser zoom and operating diagnosis completion remain unverified here.

## Possible next requests (not implemented)

- Observed verification gap: perform post-deploy operating guest/mobile and full diagnosis acceptance in the parent's accessible isolated browser.
- Expected preference request: let users pin which of several unfinished activities appears first; current rule is explicitly this-browser recent active route, then a saved activity.
- Expected content request: simplify additional lesson terminology after real beginner observation. Only the requested foundation wording was changed now.
