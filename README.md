# Chess Master Academy — Integrated Learning Edition

## Installation / deployment
- Python 3.11+; `pip install -r requirements.txt`; `python server.py` or `uvicorn server:app --host 0.0.0.0 --port 8000`.
- Render: Docker Web Service; set persistent `DATABASE_URL` pointing to PostgreSQL; otherwise SQLite is local/ephemeral.
- Stockfish installed using included Dockerfile. Check `/api/health` for active engine.
- Open `http://localhost:8000` (or deployed URL). Register code + PIN. Do not open `index.html` via file://.

## Current features
- Legal chess moves + Stockfish AI (fallback minimax if unavailable).
- Server-validated random exercise bank: procedural unique mate-in-one and material tactics generated only from legal positions, up to ~100 generated positions per bank build (actual count depends on legality and uniqueness filters); count shown at `/api/health`.
- Per-account practice sessions, spaced repetition weighting of missed positions, and test sessions where answers/hints are not exposed by API.
- Domain skill report with *provisional stage*, not a standardized FIDE/Chess.com rating. Estimated real-world Elo cannot be justified without external calibration.
- Interactive quiz assessments and curriculum gating, account persistence, desktop/mobile theme and click sound options.

## Caveats
- Generated tactical captures are heuristic; mate-in-one positions are exhaustively validated using python-chess. Capture puzzles are filtered but not guaranteed to have only one engine-optimal long-term move.
- Puzzle sessions are server validated, but client-side or automated API cheating cannot be mathematically impossible for a user with access to developer tools. Assessment rating is provisional.
- Do not modify database schemas casually. Back up PostgreSQL before deployment.
- Public production launch additionally needs rate limiting, account recovery, backups and security review.

## Test status
- Passed: Python parse/compile, Node JavaScript syntax, 24 asset files, page asset paths, synthetic question-ID uniqueness over 1,000 sessions.
- Not verified in this execution environment: import of python-chess, live API responses, real Stockfish decision quality, actual desktop/mobile browser, long-term persistence, end-to-end session correctness.
- The generated capture problems use a heuristic and must not be treated as validated unique-best-move training problems.
