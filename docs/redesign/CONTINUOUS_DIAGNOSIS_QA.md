# Continuous diagnosis and analysis release evidence

Base: PR44, `34be7806f6a6ada02d2d35c5748aceff103c573d`. Isolated local SQLite and Chromium were used; no production account reset, answer rewrite, or TEST3 mutation occurred.

## Delivered scope

| Request | Implementation and boundary |
|---|---|
| A: branch exploration | Local legal full-FEN branch board, undo/original return, explicit bounded server analysis, white POV/depth/mate/failure and cp change. Independent unanswered assessments and live AI games remain gated. Browser Stockfish worker is **not shipped**: corresponding source retrieval was blocked; no blocked route was bypassed. |
| B: continuous initial diagnosis | Next continues across internal eight-item sessions, with confirmed storage/read, route and duplicate guards. Explicit later/pause and resume remain. |
| C: held 46/48 | Separate finite technical replacement budget for new courses; explicit one-time inventory-checked supplement for held courses, with archived original baseline. Synthetic 46/48 verified; actual TEST3 cause unknown. |
| D: TEST3 audit | Blocked by unavailable authorized record access. Logs with TEST3 filter returned no entries, not proof of no records. See dedicated audit document. |
| E: alternate answers | New policy proves bounded mate alternatives against all legal defenses (at most three remaining own moves). Incomplete proof is unknown. Observable execution rubric is separate from numeric scoring. General non-mate alternative-goal classification and numeric partial-credit calibration remain unsupported. Old sessions retain old policy. |
| F: diversity | Actual bank overlap audit published. Existing exact-position/item exclusions remain; similar motifs still occur. No cosmetic mirroring or unvalidated diversity weighting added. |
| G: move sound | Shared applied-move tap across activity/replay boards, mute/volume/trusted-gesture behavior and duplicate-render suppression. Physical speaker quality and real-device autoplay not verified. |

The internal 1–3000 formula remains basic40/applied60 linear performance within the observed scope. It is not calibrated difficulty-adjusted ability or Elo. Existing scores and versions are preserved.

## Validation evidence

- Final local UI batch: **36 passed**, `/tmp/continuous-ui-final.xml`: six viewport/zoom branch cases, full-FEN legality/undo, analysis delay, exposure retry/persistence, initial continuation/anonymous/accessibility and sound.
- Full real local API/Chromium initial48 → result → reviewed baseline → matched training → reload: **1 passed**, `/tmp/initial-bc-full-paced.log`, 308.31s with deliberately paced 1.5s actions to respect existing request limits. This is not a latency benchmark.
- Final backend and packaging batch: **66 passed**, `/tmp/continuous-release-backend.xml`, including initial model/continuity, alternatives, exposure ownership, training provenance, study evaluation and Docker COPY payload/index generation/import (not a Docker image build or production PostgreSQL test). Real Stockfish covers the supplied screenshot-derived pawn ending and white-perspective output; it is not identified as a TEST3 item.
- Earlier broad backend run: 79/80 passed; sole stale imported-module assertion was resolved by rerunning current baseline-history code. Earlier selector/wording test fixture failures were corrected. No failing result is described as a pass.
- Independent review found pending exposure ownership and non-diagnosis preflight gaps. Scoped guards now cover training, challenge and legacy/V9 scored puzzles as well as diagnosis. Pending-ledger regression: **11 passed**, `/tmp/branch-finalguard2.log`, including unresolved old-token ownership after rotation and failed exposure save preventing a new grading/start request. Delayed-save navigation cancellation is also covered. Final independent review confirmed the grading/ownership blockers resolved; a remaining stale V8 failure message was guarded before release. No global API wrapper or ownership reassignment is used.

Local browser sizes include PC1366×768, short desktop, mobile360×800/390×844, landscape and zoom. These are Chromium emulations, not real mobile devices or novice observation. Production new48 completion, TEST3 audit, production branch evaluation/sound and original screenshot pixel comparison remain unverified. Previously observed production API latency is not claimed fixed. Production proxy403 was not retried or bypassed.

## Component evidence

- [Continuous initial flow](CONTINUOUS_INITIAL.md)
- [Branch exploration, gates and distribution](BRANCH_EXPLORATION.md)
- [Alternatives and diversity](GOAL_ALTERNATIVES_AND_DIVERSITY.md)
- [Move sound](MOVE_SOUND_QA.md)
- [TEST3 access and required evidence](TEST3_READONLY_AUDIT.md)

Deployment should be verified against the merged commit on the existing Render service; a successful local test alone is not operational UI validation.
