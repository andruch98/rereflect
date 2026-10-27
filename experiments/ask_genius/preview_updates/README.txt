BOOMSAY — ASK GENIUS IMPROVEMENTS

This updates application source only. Your existing OpenAI key, AI configuration,
Docker networks, login, saved reviews and conversation history are preserved.
It does not prompt for a key or make a model request. On the next startup, the
existing database migration step adds an empty field for each user's optional
saved time-period preference. Existing records are not rewritten.

1. Unzip the update and keep your existing boomsay-dashboard-preview folder.
2. Open Terminal in that EXISTING preview folder.
3. Type python3 followed by a space, drag update-preview.py from this update
   folder into Terminal, and press Enter.
4. Run: bash start-local.sh
5. Open http://127.0.0.1:53004/ask-genius with your existing login.

The updater preserves the previous application in backup-before-genius-improvements.
Any earlier backup-before-genius-layout folder is kept separately.
Rerunning a completed update is safe. Run only one updater at a time. If it
reports an unsupported preview or an existing unfinished backup, keep the folder and
ask for help; do not delete private files or the database volume.

Choose a time period before asking a question. To use all imported pilot reviews
whose original dates are missing, explicitly choose "All available history."
Choosing a dated period does not invent dates or include undated reviews.
Save a preferred period only if you want it used for new conversations.

Ordinary updater failures restore the original application and metadata before
startup has run. A forced
shutdown during a multi-file update may require recovery from the source backup.
Docker/Mac startup is not tested in the preparation workspace; startup retains
your existing local verification checks. This update does not enable AI if your
preview was not already configured.

The source backup does not contain a database backup. After startup applies the
new migration, do not simply restore the older app folder: its migration history
does not know the new database revision. Keep both folders and ask for recovery
instructions. Do not delete the database or preference field to undo the update;
the field may contain saved preferences.
