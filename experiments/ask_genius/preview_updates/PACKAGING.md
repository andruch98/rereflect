# Ask Genius context updater packaging

The updater replaces application source and its archive/metadata only. It never
reads AI credentials or login files, changes Compose/network configuration,
starts Docker, or makes a model request. `backup-before-genius-context-update` avoids
colliding with the prior review-links, chat, layout and improvements updates.
All previous backup folders remain untouched.

Both recognized `start-local.sh` versions run `python -m alembic upgrade head`
before restore/API startup. The updater pins their known hashes and requires the
new runtime and migration files in the source archive. On the user's next normal
startup, any pending migrations add the saved-period preference (on older previews),
`conversations.is_pinned` and the table for frozen public share snapshots. The
archive must contain both migrations and the sharing model/service. No
installer-side SQL or restamping is needed. This round introduces no new migration.
Automatic updater rollback covers file-update failures before startup, so it never
changes the database.
After migration, restoring old source alone is not a supported rollback: its
Alembic tree lacks the new revision recorded by the database. Preserve backups
and the migration chain for recovery rather than dropping fields or share records.

After the final application commit exists locally, run:

```bash
python3 experiments/ask_genius/preview_updates/build-update.py \
  --commit FULL_FINAL_COMMIT_SHA \
  --output /absolute/path/boomsay-genius-context-update.zip \
  --verification-log /absolute/path/offline-checks.txt
```

The ZIP contains the `boomsay-genius-context-update` folder. The builder first checks
that the builder, updater and README match the selected commit, then archives that
commit's allowlisted application paths, verifies
archive entries, writes `update.json` with the commit and SHA-256, and includes
only the updater, README and optional offline verification log. It does not
package an existing preview, uncommitted source, keys, environment files or
private records. It refuses to overwrite an existing output.

Supported bases are listed in `build-update.py`: all previously supported preview,
layout, improvements and chat releases, plus the installed review-links release
`b28bf174078fcb94438fb5f806321cc49a99c7f4`. The local-only layout commit retains
its verified archive SHA-256 requirement.
The generated ZIP, source archive and update manifest remain outside Git.

Run offline tests against the delivered public BoomSay preview skeleton:

```bash
BOOMSAY_LAYOUT_BASELINE=/path/to/known-public-preview \
  python3 experiments/ask_genius/preview_updates/verification/test_update.py
python3 experiments/ask_genius/preview_updates/verification/test_build.py
```

Tests use copies of public skeleton files plus synthetic private records and
credentials. They check preservation, both startup variants, migration-file
presence, supported-release compatibility, coexistence of all four previous
backup folders, idempotence and rollback. Include the
final test log, not temporary fixtures or private files, in the ZIP. These tests
do not establish real Docker/Mac startup, PostgreSQL migration execution or model
answer quality.

This release packages the persistent missing-period cue, consolidated instructions
with distinct examples, substantive topic-frequency guidance and context-preserving
per-topic review evidence. Existing saved message text is not rewritten.

Public share routes are accessible without login, but the Mac preview's
`127.0.0.1` origin is reachable only on that Mac. An incognito window can validate
unauthenticated access locally; sharing across devices requires a reachable
deployed origin. The updater does not expose the local server or alter its
network configuration. Link management and revocation are outside this MVP.
