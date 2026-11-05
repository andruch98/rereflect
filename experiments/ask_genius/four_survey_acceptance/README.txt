BoomSay PR #12: November 5 four-survey test

Keep Docker Desktop and your existing local BoomSay preview running.
Extract this ZIP into Downloads, then run:

python3 "$HOME/Downloads/boomsay-pr12-four-survey-test/run-local.py"

Four records only: nov5-maintenance-1, nov5-maintenance-2,
nov5-pre-renewal (9-month), nov5-move-in. All must be submitted on
November 5, 2026 in America/New_York. Missing/wrong records stop the run.

14 questions: 12 in one new conversation, then 2 independent fresh-chat
comparisons. At most 14 model calls; count questions normally run locally.
Existing provider/model/API configuration is used. Normal model charges apply.
No automatic retries; stop at the first request or validation failure.

This runs the exact PR12 application source at ddc0b2cb2dbeca7f7fc245881cd7ae87ef50987c,
including the complete approved survey example bank. It reads only the four
selected source records, disconnects from the original database, then calls
the unchanged question route against a temporary in-memory copy.

It does not install the PR, rebuild the app, send email, edit source surveys,
save chats in your dashboard, or create a Share link. Those UI checks remain
separate. This measures current answer accuracy, not a paired old/new experiment.

Answers print in Terminal. The generated Ask-Genius-Results-*.zip contains a
readable report, original source questions/answers/context, complete actual
model messages and raw replies, validation/rejection details, available token
usage and the exact tested code. Cost is marked unavailable when not reported.
Human factual assessments remain pending. Report any missing/incomplete capture.
Private survey context may include contact information; send the ZIP back here
for review, not to a public issue. No API keys or live survey URLs are exported.

The launcher prevents an accidental second paid run. If it stops, send the
saved report/error before trying again. Do not delete TEST-STARTED.txt yet.
