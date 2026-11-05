BoomSay PR12 — round 2 continuation runner, November 5 2026

Use the SAME four already-submitted round2 surveys. Do not send new survey emails.
Keep Docker Desktop and your existing preview running.
Extract this new package into Downloads/boomsay-pr12-round2-continue.
Leave the old package and result ZIPs intact.

Run:
python3 "$HOME/Downloads/boomsay-pr12-round2-continue/run-local.py"

This starts all 15 questions in new diagnostic chats; it does not resume an old chat.
At most 15 model calls, no automatic retries. Normal model charges apply.
An answer-generation or validation failure is saved and later questions continue.
Configuration, access, unexpected errors or manual interruption still stop the run.
A completed run with failures is labeled as such, not as a passing test.
Reports flag subsequent questions whose conversation history contains failed questions.
Captured refusal text is available for human review, never treated as an accepted answer.

The original preview database is read-only. Only the four named November 5 finalized
fictional submissions are copied into a temporary database for the actual PR12 route.
The package contains the application source identified by source.json.
The existing preview installation and survey records are unchanged.
The final two questions use fresh chats without previous failed answers.
No application install, dashboard chat writes, emails or browser Share tests occur.

Return the generated Ask-Genius-Results-*.zip for review. It contains original answers,
actual model requests, raw responses, failures and available token usage.
Cost is unavailable unless captured. Human factual approval remains pending.
TEST-STARTED.txt prevents accidental repeat paid runs. Previous result ZIPs are preserved.

FIVE-QUESTION SUMMARY CHECK (package named boomsay-pr12-summary-check)
Extract to Downloads/boomsay-pr12-summary-check, then run:
python3 "$HOME/Downloads/boomsay-pr12-summary-check/run-local.py"

Uses the SAME four submitted round2 surveys. No new emails or submissions.
Five questions maximum, one call per question, no retries. First three form a new
conversation; last two are fresh chats. Earlier long-chat history is not replayed.
The complete original survey evidence, model setting remain. The bank preserves its previous eight examples and adds Example 9.
For broad summaries the model writes brief source-linked findings for all four
surveys before its answer. The app checks complete survey coverage and valid question
references, not the truth/completeness of the findings or final prose. Findings are
captured in the report, not displayed in the manager chat or reused as chat history.
The output allowance is 1,840 tokens per four-survey summary request (previously
1,200) to fit these notes; actual usage is captured. This is one call, not a second
analysis service. There is no automated factual judge or automatic paid retry.

Acceptance: both repeated attention lists and the improvement/overall summaries
must preserve the missing second fob, rude-but-resolved maintenance, and the broad
community-conditions departure reason. Do not invent a specific noise/parking cause
or infer a rent-value complaint from Rent and fees. Any software failure is a failure.
Stop after these five questions and return the results ZIP for human review.
Harmless field/optional-value variations and displayed-answer quotations are now handled.
Concise answer lengths are writing targets; missing output and incomplete survey coverage
still fail. Provider refusals are reported separately. Example 9 uses this cohort, so
this is a regression check, not a blind test on unseen surveys.
