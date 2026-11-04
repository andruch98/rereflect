# Point 1: survey selection

November 4, 2026. Branch: `fix/ask-genius-survey-selection`, based on PR #11's
verified head `2498bb591c55acec9f45c16e8688dd80933161c2`.
Merge and deployment remain pending approval.

## Problem and resulting behavior

After maintenance, “what does the move in completed say” retained maintenance.
After 6-month, “which are the bad surveys, summarize them in a list” retained
6-month. Ordinary named-type descriptions now select that questionnaire's
original answers. Broad unqualified evaluations clear the prior questionnaire
filter, within the selected period. Explicit named types take precedence.
Short follow-ups retain the current subject; topic mentions such as “all
surveys about maintenance” do not select a questionnaire type.

Only the survey selection parser changes in production. Original answers,
period filters, source authorization and existing records use the existing
reader. No summary instruction, model/provider, email/draft status, property
name, database schema or infrastructure change is included.

## Validation

| Check | Observed result |
| --- | --- |
| New targeted cases on unchanged published parser | 11 failed, 2 passed |
| Targeted cases after correction | 13 passed |
| Existing Ask Genius route/service suite plus new cases | 247 passed |
| Survey workflow suite | 84 passed, 4 PostgreSQL-specific skips |
| Strengthened maintenance switch from 6-month, after full run | 1 passed |
| Whitespace/diff check | Passed |

The exact 14-question user sequence is included in the tests. It selects nine
fictional submissions in all-history scope, three in maintenance scope and one
for each other type. Model generation is mocked; routes, auth, saved chats,
record selection and original-answer payloads are real. The first count is
application-calculated. Neutral mocked prose does not establish live model
factual accuracy. The maintenance-switch parameter was strengthened after the
full run, then verified separately; the other cases were unchanged.

Full raw test inputs/outputs, rejection diagnostics, failed baseline and logs
are retained privately for the user. This public change contains no capture
archive or model-request logs. No live model/email calls, Mac installation,
merge or deployment occurred. Full repository CI is separate from these local
checks and is not yet claimed as passed.

## Next action

Review Point 1 and arrange the guarded Mac preview update/manual check before
treating it as accepted. The original move-in response should remain overall
3, apartment condition 2, unresolved No, comment “all good.” A broad request
after 6-month must include the older maintenance submissions. Actual model
summarization can still fail independently. Address broad-summary omissions
and overstatement as the next separate point.
