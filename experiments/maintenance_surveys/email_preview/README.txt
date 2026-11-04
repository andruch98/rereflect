BoomSay: seven lifecycle survey email tests

Uses the ORIGINAL preview on port 53004, preserving its database, login, private
AI settings and old source backups. The separate 53104 preview is unchanged.
The property-name label remains unchanged until approval.

SETUP
Download/unzip boomsay-lifecycle-email-update.zip into Downloads.
Keep Docker Desktop open. Run:
cd "$HOME/Downloads/boomsay-dashboard-preview" && python3 "$HOME/Downloads/boomsay-lifecycle-email-update/update-preview.py" && bash start-local.sh
Wait for startup, then open http://127.0.0.1:53004/ask-genius with your OLD login.
Confirm previous records appear and Ask Genius is connected before sending.
If startup fails or old records are missing, STOP and share the nonsecret error.
Do not delete folders/volumes or reset anything. Unknown versions/files are
refused. Source backup: backup-before-lifecycle-email-test-update.
This is a source backup, not a newly verified database backup.

Run ONE survey command, complete its workflow, then run the next:
bash "$HOME/Downloads/boomsay-lifecycle-email-update/test-survey.sh" move_in_completed
bash "$HOME/Downloads/boomsay-lifecycle-email-update/test-survey.sh" maintenance_completed
bash "$HOME/Downloads/boomsay-lifecycle-email-update/test-survey.sh" lease_month_3
bash "$HOME/Downloads/boomsay-lifecycle-email-update/test-survey.sh" lease_month_6
bash "$HOME/Downloads/boomsay-lifecycle-email-update/test-survey.sh" lease_month_9
bash "$HOME/Downloads/boomsay-lifecycle-email-update/test-survey.sh" lease_renewed
bash "$HOME/Downloads/boomsay-lifecycle-email-update/test-survey.sh" move_out_completed

Each command displays one invitation, asks you to type SEND, then prompts for
your Resend API key invisibly. The key is not saved or passed to Docker.
Only recipient: andres.feuerberg.ch@gmail.com.
Sender: BoomSay <andres@boomsay.com>.
Stable lifecycle-review test IDs create one new fictional survey per type.
Opt-out, duplicate, completed-survey, reservation and idempotency guards remain.
If send fails/times out, STOP and check Resend Emails. Do not change the test ID
or reset a status to force another email. Acceptance does not prove delivery.
Check inbox/spam and open links on THIS MAC with Docker running.

COMPLETE WORKFLOW FOR EACH TYPE
1. Choose All available history in Ask Genius and record the current submitted
count for this type. Existing maintenance answers may already be present.
2. Open Take survey in the email. Answer one question and add a distinctive
comment, such as "LIFECYCLE TEST move-in: cabinet still loose."
3. Save draft, reload and confirm your exact answers remain.
4. Ask Genius for the submitted count again: a draft must not increase it.
5. Finish and submit. Reopen the link: expect confirmation, not a second answer.
6. At http://127.0.0.1:53004/surveys filter the type, open this new Andres
(fictional email test), unit EMAIL-TEST row and verify original answers,
comment, event context and submission date.
7. Ask Genius:
"How many [survey type] surveys were submitted?"
"What did I say in the latest [survey type] survey? Show the original answers."
Compare the answer and source link with your actual answers; count should rise
by ONE from your baseline. Take screenshots and record any factual errors.
8. Keep month9 renewal intentions separate from completed lease renewal.
After all seven, ask for submitted counts by type and compare with the dashboard.

This tests manual local delivery and survey/Ask Genius behavior. It does not
test automatic reminders, PMS triggers, production delivery or cloud hosting.
Software packaging checks do not prove actual Mac startup, Gmail delivery,
answer persistence or AI accuracy. These remain your manual acceptance steps.
After you approve the tests, fix/check the property label and merge the approved
release. This package does not merge anything.
