BOOMSAY — MAINTENANCE SURVEY SOURCE UPDATE

This package replaces application source only. It preserves the existing preview
database volume, credentials, login, review analysis, conversations, AI settings,
Compose configuration and startup scripts. It neither starts Docker nor sends an
email nor makes a model request. It does not access your private credential files.

1. Unzip boomsay-maintenance-survey-update.zip beside your existing preview.
2. In Terminal, change to your EXISTING preview folder, normally:
   cd "$HOME/Downloads/boomsay-dashboard-preview"
3. Run the updater from the unzipped package, for example:
   python3 ../boomsay-maintenance-survey-update/update-preview.py
4. Run your existing startup command:
   bash start-local.sh
5. Open http://127.0.0.1:53004/surveys and use your existing login.

Normal startup rebuilds source and runs Alembic upgrade head against the EXISTING
database. Do not reset the database, remove Docker volumes, rerun a fresh installer
or recreate credentials. The source backup is backup-before-maintenance-survey-update;
previous update backups remain untouched. Repeating a completed update is safe.

The updater accepts recognized source releases and known startup scripts only.
An unsupported version or modified manifest is rejected before any write. Keep the
preview and error message for review; do not edit checksums to bypass a rejection.

Read handoff/HANDOFF.md for verification results and handoff/integration-guide.md
for simulation and questionnaire use. Readable fictional events and answers are
included under handoff/fixtures/. These documents come from the exact feature
commit recorded in update.json; uncommitted local edits are never packaged.

The independent fictional Docker Compose demo must run from the FULL feature
checkout, which contains experiments/maintenance_surveys/compose.yml. The installed
preview's source-only app/ folder and this update ZIP are not a full checkout.
Use the accompanying feature repository/bundle for that separate demo; do not run
its initializer against the installed preview database or copy private credentials.

Simulation calls the real ingestion workflow and records a simulated invitation.
It never contacts Resend, even when a real API key exists. Ask Genius itself uses
your existing AI configuration when you explicitly ask it a question; offline
tests use mocked model responses and do not establish live AI answer quality.

Rollback during updater file failures restores the original source. This backup
contains source metadata, not a database backup. Once startup applies new additive
migrations, restoring older application source alone is unsupported because its
migration tree does not know the new database revision. Keep all backups and the
migration chain for recovery. Never remove the database to undo an update.

The updater's automated checks use a synthetic preview skeleton. Installed Mac
preview compatibility and Docker startup must be verified on the user's Mac;
the preparation environment has no access to that installation.
