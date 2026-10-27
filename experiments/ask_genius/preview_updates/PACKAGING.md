# Ask Genius improvement updater packaging

The updater replaces application source and its archive/metadata only. It never
reads AI credentials or login files, changes Compose/network configuration,
starts Docker, or makes a model request. A new backup directory avoids colliding
with a previously installed layout update.

Both recognized `start-local.sh` versions run `python -m alembic upgrade head`
before restore/API startup. The updater pins their known hashes and requires the
new runtime and migration files in the source archive. On the user's next normal
startup, the new migration adds the nullable `users.ask_genius_default_period`
field. No installer-side SQL or restamping is needed. Automatic updater rollback
covers file-update failures before startup, so it never changes the database.
After migration, restoring old source alone is not a supported rollback: its
Alembic tree lacks the new revision recorded by the database. Preserve backups
and the migration chain for recovery rather than dropping the preference field.

After the final application commit exists locally, run:

```bash
python3 experiments/ask_genius/preview_updates/build-update.py \
  --commit FULL_FINAL_COMMIT_SHA \
  --output /absolute/path/boomsay-genius-improvements-update.zip \
  --verification-log /absolute/path/offline-checks.txt
```

The builder archives the exact commit's allowlisted application paths, verifies
archive entries, writes `update.json` with the commit and SHA-256, and includes
only the updater, README and optional offline verification log. It does not
package an existing preview, uncommitted source, keys, environment files or
private records. It refuses to overwrite an existing output.

Supported bases are listed in `build-update.py`: the four earlier preview/Ask
Genius versions and `5b39b14ff540b2d2de57f90fe8390b7040d2d16f` (the layout update).
The generated ZIP, source archive and update manifest remain outside Git.

Run offline tests against the delivered public BoomSay preview skeleton:

```bash
BOOMSAY_LAYOUT_BASELINE=/path/to/known-public-preview \
  python3 experiments/ask_genius/preview_updates/verification/test_update.py
python3 experiments/ask_genius/preview_updates/verification/test_build.py
```

Tests use copies of public skeleton files plus synthetic private records and
credentials. They check preservation, both startup variants, migration-file
presence, previous backup coexistence, idempotence and rollback. Include the
final test log, not temporary fixtures or private files, in the ZIP. These tests
do not establish real Docker/Mac startup, PostgreSQL migration execution or model
answer quality.
