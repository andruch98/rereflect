# Email preview verification

Scope: one explicit real-email test from the existing preview, to the approved
Gmail recipient only. Fictional PMS event; original records retained. No automatic
sender, broad permission change, network/config mutation or stored provider key.

Underlying gap: existing ingestion deliberately simulates sending and the API
container network is private. A Mac-side helper calls the existing preview for
survey creation/reservation, then sends the approved payload over HTTPS. The
backend provides a one-recipient typed event variant without weakening the public
simulation route's .invalid-only address schema. One conditional database update
claims the attempt; repeated/concurrent claims cannot both succeed. No automatic
retry. An uncertain result stays blocked. Provider idempotency is additional
protection, not the durable duplicate boundary.

Official transport reference: https://resend.com/docs/api-reference/emails/send-email
POST /emails with from, to, subject, text, html; Bearer authentication. Redirects
are rejected. No real provider requests were made during tests.

First attempt: test-file/run command used the wrong working directory; neither
file creation nor pytest executed. Corrected working directory. First executed
suite: 8 failed, 2 passed (first.txt): existing public event schema correctly
rejected Gmail. Corrected by introducing a CLI-local exact-address Literal field;
public HTTP schema and simulator remain unchanged. Second: 10 passed (second.txt).

Tests cover idempotent prepare, persisted reservation across sessions, acceptance,
explicit second test, opt-out, completed survey, wrong recipient, non-preview
refusal, mocked provider acceptance/timeout/malformed response, acknowledgement
failure and redirect rejection. Mock requests contain the exact approved payload;
fixtures/test code is committed. No LLM requests/outputs, token usage or model cost
apply. Synthetic provider receipt: fictional-receipt. No API keys captured.

Human assessment: email matches the approved wording and fixed addresses; links
use the existing local survey/unsubscribe routes. Software test success is not
proof of Mac startup, live provider acceptance, Gmail delivery or AI accuracy.
Those remain user-side verification. PostgreSQL concurrency tests are skipped
without a PostgreSQL URL; compare-and-set behavior is tested across SQLite sessions.

Final bounded results: surveys 45 passed / 4 PostgreSQL-only skips; Ask Genius
219 passed; updater 9 passed; exact-commit packager 7 passed. Logs retained beside
this record. New backup name avoids colliding with the installed answer-recovery
backup. No real model/provider requests and no Mac installation executed here.
Additional route verification: 11/11 email tests passed after adding a real HTTP
submit/unsubscribe test for the emailed link. The new test verifies persisted
original answers and that unsubscribe blocks a deliberately named second test.
No production code changed after the full survey and Ask Genius suite runs.
