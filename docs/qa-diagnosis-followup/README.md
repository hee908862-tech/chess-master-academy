# PR39 operating follow-up: progress, conflicts and partial reads

Baseline main/Live: `c8d20c601e2b4aa1933cc92c9f9cd86df367173c` (PR39). No open PRs or initial local changes. No applicable repository AGENTS.md / .agents skill file was present.

## Evidence and scope

Parent operating-browser observations (not independently repeated on production here):
- Four-question partial diagnosis: body progressed to 2/4 while the upper resume card remained 1/4.
- A saved unfinished training prevented scoped recommendation start. Records remained intact, but the confirmed conflict was also displayed as unknown processing/save outcome.
- Completing that earlier training and then the recommended new position worked, including the completed recommendation label. The underlying completion/scoring behavior is retained.
- Account checking and general progress-read failure remained visible around 19:42–19:48 UTC despite successful diagnosis/training writes. Production network/server cause is not established.

## Changes

- The resume card subscribes to the controller's rendered progress as well as active/complete visibility. The controller rejects lower revisions of the same session. Home observation ignores reads begun before a diagnosis write and superseded reads.
- Scoped start first reads current training. A known unfinished active/path/paused conflict keeps the existing session and offers continuing it, returning to diagnosis, and retrying the selected original recommendation after completion. Nothing is automatically discarded, replaced or started on completion. The pending reference stays in memory for the current identity while account lookup is unconfirmed; once confirmed it can be stored in sessionStorage per account code; no token is added to that storage. Account identity must match before it is shown.
- The scoped endpoint returns a machine-readable 409 code for active/paused conflicts. A confirmed conflict is distinct from transport failure or unknown write outcome. Race-time conflicts are handled too; a failed follow-up read is labeled as an existing-training read failure, not an unknown recommendation save. Unknown transport results still show the existing uncertain-save treatment and require state confirmation.
- Bootstrap tracks failures per read. Confirmed progress remains actionable; a separate notice identifies failed account/foundation/diagnosis/training/game reads, exposes the actual error, and retries only failed reads. A later successful read clears only that read's error. Successful writes are not treated as proof that every unrelated read succeeded.
- The account badge no longer silently remains “checking” after account read failure. A visible retry and explicit failure label are provided. Later successful account reads update the badge, including reads initiated outside the original refresh controller. Stale failures and identity changes cannot overwrite the newer identity's display.

No score/rating, answer criteria, content, stored learning schema, original reports, authentication protection or deployment configuration changed. The only server response change is typed metadata for two existing conflict rejections.

## Validation

**73 distinct selected tests passed, no unresolved failures or skips** ([case list](checks.txt)). New real-API browser coverage includes a four-question 3-success/1-skip diagnosis, header progress/reload/completion, preservation of existing training, completion followed by the exact pending recommendation, and returning to its completed result. Controlled boundary coverage separates a race-time confirmed 409 from network failure, partial GET failures from healthy progress, and an old delayed diagnosis read from a new confirmed revision. Existing guest linkage/logout and account-switch tests are retained.

Physical devices and this executor's operating UI are not tested. The prior executor Live request failed at the outbound proxy (`CONNECT 403`, HTTP `000`); it is not repeated or bypassed. Parent operating observations above are labeled separately. Management API verification of the eventual Live commit is not an operating browser test.

Local checks also cover 360×800 conflict navigation, PC progress/partial failure, existing responsive flows at 1366×768 / 1180×650 / 360×800 / 390×844 / 844×390, guest link/logout/other-tab denial, late account responses and training continuity. Mobile sizes are emulated. A race-test assertion was corrected to inspect the account retry on home: the pre-existing practice layout deliberately hides the global header. The stale failure itself remained preserved. JavaScript syntax, diff whitespace and staged Docker COPY/index/import checks passed. No local Docker image build is claimed.

The current production failing endpoint could not be identified from the supplied observation alone; this change exposes failed-read names rather than assuming a server outage or infinite loading. The parent can recheck the exact operating failures after deployment. Deployment commit and Live status are recorded in the PR/final handoff.
