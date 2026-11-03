BOOMSAY — SURVEY CONTINUITY UPDATE (EXISTING MAC PREVIEW)

This is an update for your existing BoomSay preview at port 53004.
Keep Docker Desktop running. Unzip this package in Downloads.

1. Paste this block into Terminal:

   cd "$HOME/Downloads/boomsay-dashboard-preview" &&
   python3 "$HOME/Downloads/boomsay-survey-continuity-update/update-preview.py" &&
   bash start-local.sh

2. After startup succeeds, open:
   http://127.0.0.1:53004/surveys
   Use your existing login.

3. To try one fictional maintenance survey in that same preview, run:

   cd "$HOME/Downloads/boomsay-dashboard-preview" &&
   docker compose -f compose.json exec -T api python -m src.survey_preview

   Terminal prints the private survey link. Open that link in your browser.
   This creates Jamie Example (fictional), unit DEMO-204, ticket DEMO-WO-1001.
   It records a simulated invitation: NO EMAIL IS SENT.
   Repeating this command returns the same survey and preserves saved answers.
   It cannot initialize/reset your community or alter your login/AI settings.

4. Answer 2 — Bad; No, still unresolved; Not sure; and add a fictional comment.
   Wait for Draft saved, reload to check it, then submit. In Surveys, confirm
   the submitted status and open View answers.

5. In Ask Genius, choose All available history and ask:
   How many survey responses did we receive during this period?
   What did residents say in surveys about their maintenance experience?
   Show each answer.
   Check that the relevant question/answer opens in a popup under its topic.
   View all answers from this survey should expand inside that popup.

The count is computed from submitted surveys without an AI request. Narrative
questions use YOUR EXISTING configured model and can incur its normal usage costs.
This update does not change that configuration or replace your model with a mock.
The automated checks used mocked model answers; live AI quality remains untested.

The updater preserves database storage, saved reviews/analysis, chats/defaults,
login, private configuration, Compose and startup scripts. It backs up application
source to backup-before-maintenance-survey-continuity-update. Earlier backups
remain intact. A repeated completed update is a no-op. Unsupported versions are
rejected before changes; do not edit checksums or remove backups to bypass checks.

Startup uses your existing migration command. Survey migrations are additive.
The source backup is NOT a database backup; restoring old source after applying
migrations is not a supported rollback. Never use down -v or reset the database.

This delivery was NOT installed on your Mac. Docker/ARM startup and browser visual
verification could not be completed in this environment. Relevant automated tests
passed. The full production build remains blocked by pre-existing unrelated
TypeScript errors. Your existing preview uses its existing startup method.

Exact commit and checksum: update.json. Current scope, test results and limitations:
handoff/HANDOFF.md. Older verification documents are historical, not a fresh test.
