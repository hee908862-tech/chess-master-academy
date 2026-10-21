# Home foundation follow-up to PR #32

Baseline: `8a21c4e793fd75d66c2c16c786b4e94e8275a5c8`.

| Saved state | Home action | Destination |
| --- | --- | --- |
| New learner | 기초 배우기 시작 | Recommended course/list |
| Active lesson | 이어서 배우기 | Saved practice |
| Some courses completed, no unfinished lesson | 이어서 배우기 | Next recommended course/list |
| All courses completed, no unfinished review | 기초 복습하기 | Expanded course list |
| Historically completed course with unfinished review | 이어서 배우기 | Saved review practice |

Completed courses retain their historical completion flag during review. The home action therefore also checks the saved step and solved state. Opening the course list never starts or resets a course. No server, database, scoring, account, or deployment configuration changes are included.

## Local validation

62 unique tests passed: 60 related regression cases plus a final 10-case home matrix rerun (8 overlap). Suites: home foundation follow-up, first visit browser, focused learning follow-up, foundations, growth cycle, academy upgrade browser. One existing Starlette/httpx deprecation warning. JavaScript syntax and git whitespace checks passed.

The home matrix uses new local accounts and real local APIs, five progress states at widths 390 and 1180, reloads, destinations, and horizontal overflow checks. It asserts identical account, foundation, and active diagnosis snapshots before/after navigation and zero write requests. All data uses disposable local SQLite files, not production accounts. Existing guest and balanced diagnosis 1–3000 regression coverage also passed locally.

## Operational validation limitation

The production request to `https://chess-master-academy.onrender.com/api/health` failed at the environment CONNECT proxy: curl exit 56, `CONNECT tunnel failed, response 403`, reported HTTP 000. This is not an application HTTP 403. No alternative network path was attempted.

The requested production guest flow, mobile UI, and separate test-account diagnosis completion/1–3000 result remain **unverified**. No production test account was created and the existing QA account or its active diagnosis was not accessed. Render management deployment status is a separate check and does not establish those interactive results.
