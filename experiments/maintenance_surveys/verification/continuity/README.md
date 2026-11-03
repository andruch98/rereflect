# Survey continuity correction — verification, 3 November 2026

Correction branch: `fix/survey-genius-continuity`, based on
`ccb53d4122a76ffd6045d2bf188d20dfdb712d2d`. Exact delivered source is recorded
in the ZIP's `update.json`. No merge, deployment, Mac installation, real email or
paid model call was performed in this correction session.

## Bounded scope and final results

| Check | Final result | What this establishes |
| --- | --- | --- |
| Ask Genius offline suite | 191 passed | Source continuity/clarification, count semantics, evidence validation, review regressions, sharing restrictions and preview simulation preservation |
| Survey workflow suite | 35 passed, 4 skipped | Draft/final submission and workflow behavior in SQLite; PostgreSQL concurrency cases skipped |
| Related frontend tests | 122 passed, 1 skipped | Popup grouping, relevant answer first, expansion, close, chat controls and existing review behavior in the test DOM |
| Updater tests | 9 passed | Source-only update, repeat no-op, preservation, validation, failed-write rollback and archive safety |
| Packager tests | 7 passed | Exact committed files, required migrations/documents and refusal of uncommitted substitutions |
| ESLint on changed frontend files | Passed | No lint errors in those files |
| TypeScript | Blocked by existing errors | All 20 error-bearing source/test files match the survey base; no new errors reported in changed application files |
| Preview production build | Compiled; failed later type validation | Existing invalid `EvidenceCell` page export blocks completion; not a successful production build |
| Browser walkthrough | Not completed | Chromium launch blocked by environment socket restrictions; no screenshot/visual result |
| Mac/ARM/Docker | Not run | Docker unavailable here; startup on the user's actual installation is unverified |

Stop criterion: the changed-flow suites and source updater/package checks pass;
record environment/pre-existing blockers instead of broad unrelated refactoring.
The downloadable delivery report adds the exact ZIP replay result and remote
commit/PR after packaging. The ZIP replay uses a synthetic installation and does
not establish actual Mac or database migration startup.

## Failed attempts and resolutions

- Initial baseline survey checks: 20 passed before edits. Console result was seen;
  a separate baseline log was not saved.
- First backend pass: 27 failed, 153 passed. Several review tests depended on the
  old implicit review-only source. They now ask explicitly about reviews; new
  clarification tests cover source-free questions.
- Second backend pass: 2 failed, 178 passed. Fixed one remaining ambiguous test
  input and an actual defect: a generic evidence label was being validated as a
  quoted original answer during follow-ups. Missing excerpts are now null.
- Third backend pass: 1 failed, 190 passed. The new draft test incorrectly used
  POST instead of the existing PUT route. Corrected the test input.
- Fourth and final backend passes: 191 passed each. Final pass includes retaining
  topic text and exact references through an intervening count follow-up.
- First survey workflow pass: 5 passed, 34 setup errors because the temporary
  environment lacked Celery. Installed the existing declared Celery/Redis
  dependencies in the test venv; next run passed 35 with 4 skips.
- First frontend/build commands: pnpm refused externally linked dependencies;
  no tests/build ran. Used the installed Vitest/Next binaries directly.
- Frontend second pass: 1 failed, 121 passed, 1 skipped. Replaced the obsolete
  separate-page anchor expectation with topic-specific popup assertions. Final
  pass: 122 passed, 1 skipped.
- Initial build check was blocked by automatic approval review because Sentry
  could upload artifacts externally. Local preview configuration now skips
  Sentry build instrumentation/uploads, consistent with existing runtime preview
  telemetry settings. Production configuration remains unchanged. The safer
  preview build compiled, then failed the existing Next page-export type error.
- First browser harness startup failed because middleware was added after app
  startup. Corrected the temporary harness; API and Next dev servers started.
  Chromium itself then failed to launch (socket permission). No browser scenario
  ran. Temporary servers were stopped. The harness is not production auth proof.
- Packager follow-up: 5 passed, 2 errors from tests hardcoding the old bundle
  folder name. Updated tests to use the builder's actual bundle name. Final:
  7 passed. Updater final: 9 passed.

## Model inputs, outputs, rejections and human assessment

The downloadable verification ZIP includes all captured test inputs, full mocked
model request messages and outputs, application responses/rejection reasons,
failed-run logs and a readable transcript. `test-conversations.jsonl` is an
append-only capture across several test passes. It is not one live conversation
or evidence of model intelligence. Repeated tests can have earlier failing output.
Final suite logs identify the passing implementation.

Capture is partial: only calls through the instrumented fake provider and question
helper are recorded. Direct service/unit calls and the initial baseline do not
all have individual transcripts; their test inputs/assertions remain in the code.
Frontend actions are represented by test cases/logs, not browser recordings.
No human property-manager assessment or live-model factual accuracy assessment
was conducted. Assistant review assessed code/test behavior, not live AI quality.

Real model requests: **0**. Real provider token usage/cost: **not applicable**.
Any 100/30 token values are fabricated test-fixture values, not usage. Email was
simulated. Test residents, answers and identifiers are fictional. No credentials
or provider keys are included in the capture.

## Required human walkthrough

Use the existing-preview README on port 53004. Confirm prior reviews/analysis and
chats remain; original fonts render; source clarification resumes the question;
review maintenance follow-ups stay on reviews; exclusions choose one source;
submitted survey counts exclude drafts; topic links open the right original
question/answer, expand the same submission and close back to the chat.
Review-only sharing should work; survey-backed sharing remains unavailable.
Narrative questions on Mac use the existing configured provider and may incur
normal costs. They have not been run against a live provider in this session.
