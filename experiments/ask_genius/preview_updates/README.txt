BOOMSAY - ASK GENIUS REVIEW LINKS UPDATE

This updates application source only. Your existing OpenAI key, AI configuration,
Docker networks, login, saved reviews and conversation history are preserved.
It does not prompt for a key or make a model request. On the next startup, the
existing database migration step adds chat pinning and public share snapshots.
Older previews also receive the optional saved time-period preference field.
Existing reviews, analysis and message content are preserved.

1. Unzip boomsay-genius-review-links-update.zip. Its folder is also named
   boomsay-genius-review-links-update. Keep your existing boomsay-dashboard-preview folder.
2. Open Terminal in that EXISTING preview folder.
3. Type python3 followed by a space, drag update-preview.py from the new
   boomsay-genius-review-links-update folder into Terminal, and press Enter.
4. Run: bash start-local.sh
5. Open http://127.0.0.1:53004/ask-genius with your existing login.

The updater preserves the previous application in backup-before-genius-review-links-update.
Earlier backup-before-genius-chat-update, backup-before-genius-layout and
backup-before-genius-improvements folders
are kept separately. They do not block this update.
Rerunning a completed update is safe. Run only one updater at a time. If it
reports an unsupported preview or an existing unfinished backup, keep the folder and
ask for help; do not delete private files or the database volume.

You can choose a starter question immediately. Choose a time period before sending
it. To use all imported pilot reviews
whose original dates are missing, explicitly choose "All available history."
Choosing a dated period does not invent dates or include undated reviews.
Save a preferred period only if you want it used for new conversations.

Share creates a public, read-only snapshot of that chat. Anyone with its link can
view the shared messages and their attached review evidence without signing in.
Later messages are not added automatically. Managing or deactivating links is not
part of this MVP.

The preview runs only on this Mac at 127.0.0.1. You can test the shared link in a
private browser window on this Mac, but another person's computer cannot open
that local address. Sharing with others requires BoomSay to run at a reachable
hosted address. This update does not publish your preview or change its network
configuration.

Ordinary updater failures restore the original application and metadata before
startup has run. A forced
shutdown during a multi-file update may require recovery from the source backup.
Docker/Mac startup is not tested in the preparation workspace; startup retains
your existing local verification checks. This update does not enable AI if your
preview was not already configured.

The source backup does not contain a database backup. After startup applies the
new migrations, do not simply restore the older app folder: its migration history
does not know the new database revision. Keep both folders and ask for recovery
instructions. Do not delete the database, saved preferences or sharing records to
undo the update.
