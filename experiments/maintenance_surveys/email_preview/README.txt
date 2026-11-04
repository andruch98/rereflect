BoomSay: one real survey email from your existing Mac preview

This update builds on the tested survey/Ask Genius corrections. It preserves the
existing database, source backups, login, AI configuration and Compose networks.
It adds a separate email test command. It does not enable automated delivery.
The key is entered hidden in Terminal for a send, held in memory, never saved or
passed to Docker. Keep your password-manager copy. Do not share the key in chat.

1. Unzip boomsay-survey-email-update.zip into Downloads. Keep Docker Desktop running.
2. In Terminal:
cd "$HOME/Downloads/boomsay-dashboard-preview" && python3 "$HOME/Downloads/boomsay-survey-email-update/update-preview.py" && bash start-local.sh
3. Prepare the test (no email is sent):
python3 "$HOME/Downloads/boomsay-survey-email-update/survey-email-test.py" prepare

This creates one NEW fictional maintenance survey, not a duplicate of your existing
completed test. It prints the agreed email and survey link. Repeating prepare
returns the same survey. It does not overwrite answers. The manager dashboard
shows Andres (fictional email test), unit EMAIL-TEST, ticket EMAIL-TEST-first-test.

4. When ready to send the displayed email:
python3 "$HOME/Downloads/boomsay-survey-email-update/survey-email-test.py" send
Type SEND when asked. Paste your Resend key at the hidden prompt, then press Enter.
Only andres.feuerberg.ch@gmail.com is permitted; sender is BoomSay <andres@boomsay.com>.

5. Check Gmail inbox/spam and open Take survey ON THIS MAC while Docker is running.
Answer and submit, then check http://127.0.0.1:53004/surveys and Ask Genius.
Both the survey and unsubscribe links are local for this test, not public links.
Resend acceptance does not prove inbox delivery. No delivery webhook is included.

Duplicate protection: the database reserves the attempt BEFORE contacting Resend.
Repeating send cannot resend, even after restarting Terminal or after a timeout.
A crash/timeout is treated as uncertain: check Resend Emails before doing anything
else. A reservation can remain if the email was never sent; this intentionally
avoids guessing and duplicate sends. Do not reset statuses or delete records.
A deliberate later test uses a new name with --test-id second-test on BOTH commands.
Do not start another test to bypass an uncertain send or an unsubscribe.

The event remains fictional. The invitation starts simulated; an explicit send
changes it to a real test attempt (email_test_reserved, email_test_accepted or
email_test_failed). A failed/uncertain result is not a confirmed delivery failure.
Production delivery and other application emails remain unchanged. Your key is
not installed globally. No real email was sent during development verification.

Mac installation, live Resend acceptance and actual Gmail delivery still require
your test. Keep existing files/backups. Do not use Docker down -v or reset the DB.
