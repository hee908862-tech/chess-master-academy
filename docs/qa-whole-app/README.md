# Whole-app clarity follow-up (PR38 baseline)

Baseline: `632d31cf6f5a0eebdf989ea26151e1d084bcf69b` on main and Render Live before work. Existing working tree was clean. No repository AGENTS.md or skill files were present. Existing account records, grading, schema, and guest access rules are unchanged. Only the existing scoped task/completion references are additionally serialized for presentation; no migration or historical rewrite.

## Survey and information hierarchy

Local Chromium survey used a disposable guest, all destinations, a real AI game and saved-game analysis. This is an implementation audit, **not novice observation or a physical mobile-device study**.

| Screen | Main action / always shown | Expand when needed | Other destination / duplicate cleanup |
|---|---|---|---|
| Home | First visit: foundations or activity choice. Return: named recent activity or evidence-based next action | Unsaved samples; other ongoing activities; detailed activity records | Preserve free activity selection. A completed diagnosis/training may recommend its next step without being displaced by an older foundation session |
| Learn | Choose learning purpose; title and short description separated | Existing saved activity and course lists | Practice and selection remain separate routes; no new courses |
| Foundations | Direct current practice, goal/turn, board, verdict and next step | Original explanation, visual aids, accessible move list | Back to course list or learning hub; current session unchanged |
| Puzzle | General/challenge mode, then current board and core actions | Topic/difficulty selector closes only after puzzle start; rules remain available | Retain challenge and legacy behavior; no scoring changes |
| Training selection | New first-move practice, independent verification, saved practice | Records, measurement methods, previous four-step route | Explicit return to active training |
| Training execution | Public task-specific action and assessment range before board, core actions and verdict adjacent | Original task wording, concept/evidence/line; simplified wording with original text if changed | Scoped completion now returns to recommendation progress; completed task is not recommended again |
| Diagnosis selection | Three directly selectable native cards, question/time/result comparison, selected label, adjacent start | Limits and older modes | No second scope dropdown selection; novice link starts foundations |
| Diagnosis execution | Progress/turn and goal before board; next/skip/home controls | Alternative evidence and read-only replay | Existing answer, partial, uncertain and save semantics preserved |
| Diagnosis results | Evidence summary and one shared next recommendation | Item evidence, historical results, methods/comparison limits | Completion leads to new practice; no automatic growth claim or changed recheck gate |
| Opening | Board and explanatory/recall modes, move tools | Course/variation/orientation settings; longer scope and source explanation | Existing repertoire and full catalog retained |
| Game | Turn, board, hints and undo together; visible non-Elo warning | Full difficulty detail and engine badge in the existing settings disclosure; extra tools/history | Critical game controls retain their positions and strict simultaneous visibility checks |
| Review | Choose saved game first; after load, board, step controls and current explanation | Other game selection; original wording when a glossary substitution applies | Empty board controls hidden before a game is loaded; original PGN and analysis unchanged |
| Profile | One next recommendation and activity reports | Older diagnosis and game-rule statistics | Account, settings and data-management routes remain separate |
| Settings | Visible board/piece/sound and review-interval controls | Existing help, sources and licensing | Explicit account switch unchanged; no account form added to logged-in overview |

Redundant toolbar text is removed on screens already carrying the same main heading. Help controls remain available. Buttons and disclosures share keyboard focus, wrapping and touch-target treatment. Existing important storage, measurement and error information stays accessible; original educational explanations are not replaced by newly authored analyses.

## Two staged flows

1. First visit → “기초부터 배우기” → current first practical board without a second choice → rook move → saved completion → home/reload → same step/session. Existing unsaved sample remains separate and never credits formal success.
2. Click diagnosis scope card → complete a real subskill diagnosis via board moves → result recommendation with observed reason → start a **different** scoped practice position → finish through board moves → return to recommendation progress. Completion is read from existing `scoped_completed`; it does not claim growth, re-score the diagnosis, or unlock other recheck rules.

Before: scope comparison was informational and required dropdown reselection; completed scoped practice took the generic first-move follow-up; an unfinished foundation could displace the just-completed diagnosis recommendation. After: cards select directly, scoped completion has its own navigation, and recent activity determines the follow-up while other ongoing activities remain reachable.

## Initial home delay

Observed operational evidence supplied by parent: initial home stayed checking for about 14 seconds once; reload was normal. **Production root cause is unconfirmed.** Code investigation found serial `/me` then an all-results barrier and overlapping GETs from independent controllers. The new bootstrap starts independent reads together, coalesces only overlapping identical GETs within the same identity, clears entries after settlement, and never coalesces writes. Known recent activity can be used without waiting for unrelated reads; unknown recent state cannot be replaced by the first response. A four-second delay notice, bounded request timeout and guarded read-only retry preserve existing records. No load test or external analytics added.

## Historical wording

Only explicit glossary equivalents are projected: same file → same vertical line (file), file letter, back rank, discovered attack. A changed projection is labeled and the **exact original text** remains in an adjacent disclosure. Verdict, submitted/expected moves, FEN, timestamps, record content and interpretation are not altered. Unknown terminology is left untouched. Tests inject old wording into a local display to verify projection/original access and unchanged server state; this is not a rewritten production record.

## Validation

**115 distinct selected tests passed, 0 unresolved failures, 0 skips** (reruns counted once; see [case list](checks.txt)). A temporary test parametrization setup error was corrected and both viewport cases rerun successfully; it is not an application failure. Browser dimensions: 1366×768, 1180×650, 360×800, 390×844, 844×390; additional existing regression sizes and 200% zoom. Natural vertical scrolling is allowed. Real engine uses local Stockfish 17.1. No operating identities were used.

Operational functional verification is reserved for the parent's connected browser. This executor previously returned `curl: (56) CONNECT tunnel failed, response 403` / HTTP `000` at the outbound proxy for the Live URL. That is not an application 403; no bypass or repeated request was attempted in this follow-up. Render management Live/commit verification is distinct from operating UI verification.

### Regression handling and boundaries

The first runs caught two presentation bugs: a delayed recent-activity response could lose priority to a foundation read; the review disclosure initially captured execution tools. Both were corrected and exercised again. Mobile training duplicated its scope in two sentences; removing that repetition kept the original board size and restored the existing geometry checks. Long pre-game difficulty detail and the engine badge moved into the existing disclosure, while the non-Elo warning remains visible. The existing game tests retain their strict simultaneous board/turn/hint/undo assertions.

Older tests that selected controls inside closed panels were updated to **open the visible disclosure first**, including unsaved guest samples, opening course selection and another-game review. No force clicks or removed preservation assertions were used.

Packaging checks stage Docker COPY inputs, build the position index, import the staged server, and verify the new JS/CSS plus piece license assets. This is a COPY-payload smoke check, not a local Docker image build. Render's subsequent deployment is verified separately.

### Screenshots

- [First home, PC](home-first-pc.png), [direct foundations, PC](foundation-pc.png)
- [Diagnosis choice, PC](diagnosis-pc.png), [diagnosis choice, 360 wide](diagnosis-mobile.png)
- [Current training, PC](training-pc.png), [opening, 360 wide](opening-mobile.png)
- [Review, 1366×768](review-1366x768.png), [review, 360×800](review-360x800.png), [review, 390×844](review-390x844.png)

Full-page mobile captures include the fixed bottom navigation at its viewport position; natural page scrolling is tested separately. Selected screenshots are evidence, not the extent of the screen survey.

### Follow-up candidates (not implemented)

1. **Observed, cause unresolved:** remeasure the intermittent initial Live home delay in the parent's operating browser; distinguish network cold start, server and individual endpoints.
2. **Unverified:** physical mobile and novice observation of choosing a diagnosis and finding the next practice. Emulated viewport and keyboard checks do not establish real-user comprehension.
3. **Expected:** glossary requests for other old explanation terms. Add only defensible equivalents with exact original access; do not silently regenerate historical analysis.

### Final local results

- Two representative flows: direct foundation start/return and completed real subskill diagnosis → new scoped practice → completion/recommendation/reload.
- Every named destination inspected; 14 routes traversed at five viewport sizes. Actual puzzle start, game move/engine reply/resign/review, education/repertoire lessons, opening recall/branch/save, keyboard, 200% CSS zoom, promotion, cancel, motion, late responses, retry, duplicate start and identity boundaries covered by the selected browser suites. CSS zoom and viewport emulation are not native browser zoom/physical-device claims.
- Backend: scoped reference/completion, session continuity, duplicate completion and actual engine alternative judgments; Docker COPY payload/index/import and new assets.
- JavaScript syntax and `git diff --check` pass. No local Docker build, production load test, operating UI success, novice study or physical mobile success is claimed.
- Deployment: recorded in the PR and final handoff once the existing automatic deployment becomes Live. No manual deployment or infrastructure changes.
