BoomSay PR12 — round 2, four new surveys, November 5 2026

Keep Docker Desktop and the existing preview running. Extract to Downloads/boomsay-pr12-round2.
Run email commands from ~/Downloads/boomsay-dashboard-preview, one at a time:
python3 "$HOME/Downloads/boomsay-pr12-round2/survey-email-test.py" send --test-id round2-move-in --event-type move_in_completed
python3 "$HOME/Downloads/boomsay-pr12-round2/survey-email-test.py" send --test-id round2-maintenance --event-type maintenance_completed
python3 "$HOME/Downloads/boomsay-pr12-round2/survey-email-test.py" send --test-id round2-pre-renewal --event-type lease_month_9
python3 "$HOME/Downloads/boomsay-pr12-round2/survey-email-test.py" send --test-id round2-move-out --event-type move_out_completed
Verify the displayed recipient is your test email. Type SEND and enter your Resend key when prompted (hidden, not saved). Submit each survey before proceeding. These four types were randomly sampled without replacement from the seven supported types. Fill in new fictional answers in your own words.

After all four are submitted on November 5, 2026 (Miami time):
python3 "$HOME/Downloads/boomsay-pr12-round2/run-local.py"

15 questions, at most 15 model calls, no retries; stops on first failure. Uses existing configured AI; normal model charges apply. Tests only these four named submissions. Original database is read-only; question-route writes go to a temporary copy. Updated application source is included; exact commit and file hashes are in source.json. This does not install the updated dashboard or save chats there. Browser sharing remains a separate check.

Actual answers print in Terminal. Return the generated Ask-Genius-Results-*.zip for review. It includes originals, all model requests/outputs, errors, available usage and tested code. Missing cost is labeled unavailable. Human assessment remains pending. No new answer has been pre-approved. Earlier examples are guidance only. No automatic repeat run: retain TEST-STARTED.txt and share errors before retrying. No API keys are exported; report contains private survey context.
