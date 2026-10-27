BOOMSAY — ASK GENIUS LAYOUT UPDATE

This updates application source only. Your existing OpenAI key, AI configuration,
Docker networks, login, saved reviews, conversation history and database stay as
they are. It does not prompt for a key or make a model request.

1. Unzip the update and keep your existing boomsay-dashboard-preview folder.
2. Open Terminal in that EXISTING preview folder.
3. Type python3 followed by a space, drag update-preview.py from this update
   folder into Terminal, and press Enter.
4. Run: bash start-local.sh
5. Open http://127.0.0.1:53004/ask-genius with your existing login.

The updater preserves the previous application in backup-before-genius-layout.
Rerunning a completed update is safe. Run only one updater at a time. If it
reports a different layout or an existing unfinished backup, keep the folder and
ask for help; do not delete private files or the database volume.

Ordinary update failures restore the original application and metadata. A forced
shutdown during a multi-file update may require recovery from the source backup.
Docker/Mac startup is not tested in the preparation workspace; startup retains
your existing local verification checks. This update does not enable AI if your
preview was not already configured.
