BOOMSAY — ASK GENIUS ANSWER RECOVERY UPDATE

Update your existing BoomSay preview on port 53004. Keep Docker Desktop running.
Unzip this package in Downloads; keep your existing preview folder in place.

1. Paste into Terminal:

   cd "$HOME/Downloads/boomsay-dashboard-preview" &&
   python3 "$HOME/Downloads/boomsay-answer-recovery-update/update-preview.py" &&
   bash start-local.sh

2. After startup succeeds, open:
   http://127.0.0.1:53004/ask-genius
   Use your existing login. Open your survey conversation, with All available
   history selected. Your already-submitted fictional survey remains available.

3. Retry the question that failed, or send:
   What did residents say in surveys about their maintenance experience?

   Then ask:
   Show each answer.

   The summary should answer your question without an error or unwanted evidence
   controls. The follow-up should open the relevant original answers in a popup.
   Check the summary against those answers. A software test cannot establish the
   factual accuracy of a new live model response.

You do not need to create or submit another survey. Narrative questions use your
existing configured model and can incur its normal usage costs. This update does
not change that configuration or replace your model with a mock. Automated tests
used fictional data and mocked/reconstructed responses; live AI quality remains
unverified.

The fix accepts valid extra supporting references while hiding their controls
until requested, preserves them for follow-ups, and normalizes only unambiguous
JSON string line breaks. It continues rejecting invalid references, invented
quotations and broken output that would require guessing. Failures now have a
specific stored reason and a plain-English message. No automatic retry is added.
Shared instructions remain in one core, with a short survey-specific section.

The updater preserves database storage, saved reviews/analysis, chats/defaults,
login, private configuration, Compose and startup scripts. It backs up application
source to backup-before-genius-answer-recovery-update. Earlier backups remain
intact. A repeated completed update is a no-op. Unsupported versions are rejected
before changes; do not edit checksums or remove backups to bypass checks.

Startup uses your existing migration command. No new migration is added by this
fix. The source backup is NOT a database backup; restoring older source after
applying migrations is not a supported rollback. Never use down -v or reset data.

This package has not been installed on your Mac. Mac/ARM startup and live AI
responses still need your walkthrough. Earlier reports of production-build and
browser limitations are historical; this fix does not claim to resolve them.

Exact commit and checksum: update.json. Current scope and verification:
handoff/verification/answer-recovery/README.md and verification/offline-checks.txt.
Older reports bundled under handoff are historical, not freshly repeated tests.
