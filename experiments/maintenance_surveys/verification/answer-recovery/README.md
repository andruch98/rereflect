# Ask Genius answer recovery — verification scope

3 November 2026. Follow-up on correction branch fix/survey-genius-continuity,
PR #6, starting from 6dd7827360d1a370d59537a0c7407bf5ad5faeff. The delivery manifest
identifies the final source commit. No merge, deployment or Mac installation.

## Reported problem and correction

The summary question did not request evidence controls. The old validator rejected
otherwise valid supporting references returned by the model. The user's pasted
response also displayed apparent backslash/newline formatting inside JSON strings;
its original transport bytes are unavailable, so three variants are replayed.

Valid extra references are checked and retained for follow-ups, without showing
controls in the summary. Only unambiguous JSON string newline formatting is
normalized; raw provider output is retained. Truncated/ambiguous JSON, unknown
records, mismatched quotations and invalid question/topic references still fail.
Diagnostics distinguish the cause, and both immediate and reopened-chat messages
explain it in plain English. No automatic retry or additional model request is
introduced. Shared rules are kept once, with a short survey-specific section.

## Final software results

- Ask Genius offline: 219 passed, including 28 new recovery/diagnostic tests.
- Survey workflows: 35 passed; 4 PostgreSQL concurrency cases skipped.
- Related frontend: 122 passed; 1 existing saved-run test skipped.
- Source updater: 9 passed. Exact-commit packager: 7 passed.
- Changed frontend lint: passed. Whitespace/diff check: passed.
- The actual ZIP's source comparison and three-base synthetic replay are recorded
  in the delivery verification file, after the final commit is created.

## Failed attempts retained

The baseline replay against the old application had 20 failed and 1 passed tests.
The baseline includes the three rejected versions of the reported response and
new expectations that the old code did not implement. The first full run after
the fix had 208 passed and 4 failed tests: those four still expected the old generic
messages or rejection of valid unrequested references. They were updated to the
approved behavior; final checks include 7 additional boundary cases. Baseline and
first-run capture predate specific diagnostic logging; missing details are not
retrofitted as if freshly observed.

## Bounded verification

Run the Ask Genius offline suite, survey workflow suite, relevant frontend suites,
changed-file lint, updater/packager tests, then replay the actual ZIP against three
synthetic installed versions. Stop when those pass; do not expand to unrelated
features or claim a production build/browser pass.

The downloadable record includes failed baseline and intermediate attempts, final
logs, captured mocked request/response conversations, source test inputs, rejection
reasons when captured, and a readable human assessment. See the packaged
verification/offline-checks.txt for final counts and delivery checks.

## Evidence limits

All model outputs in this run are mocked or reconstructed; zero live model calls.
Tokens and cost of the user's original failed call were not provided. Do not infer
a zero cost for that historical call. Replay proves application handling, not the
factual accuracy of future AI summaries. Some direct unit-test calls do not pass
through the conversation capture; their complete inputs/expected outputs are in
the included test source. There is no original provider-byte capture from the Mac.
Mac/ARM startup and human assessment of live model quality remain unverified.
The prior continuity report's Docker/browser/build limitations are historical.
