# Ask Genius chat updater packaging

The updater replaces application source and its archive/metadata only. It never
reads AI credentials or login files, changes Compose/network configuration,
starts Docker, or makes a model request. `backup-before-genius-chat-update` avoids
colliding with either the prior layout or improvements update. Both previous
backup folders remain untouched.

Both recognized `start-local.sh` versions run `python -m alembic upgrade head`
before restore/API startup. The updater pins their known hashes and requires the
new runtime and migration files in the source archive. On the user's next normal
startup, pending migrations add the saved-period preference (on older previews),
`conversations.is_pinned` and the table for frozen public share snapshots. The
archive must contain both migrations and the sharing model/service. No
installer-side SQL or restamping is needed. Automatic updater rollback
covers file-update failures before startup, so it never changes the database.
After migration, restoring old source alone is not a supported rollback: its
Alembic tree lacks the new revision recorded by the database. Preserve backups
and the migration chain for recovery rather than dropping fields or share records.

After the final application commit exists locally, run:

```bash
python3 experiments/ask_genius/preview_updates/build-update.py \
  --commit FULL_FINAL_COMMIT_SHA \
  --output /absolute/path/boomsay-genius-chat-update.zip \
  --verification-log /absolute/path/offline-checks.txt
```

The ZIP contains the `boomsay-genius-chat-update` folder. The builder first checks
that the builder, updater and README match the selected commit, then archives that
commit's allowlisted application paths, verifies
archive entries, writes `update.json` with the commit and SHA-256, and includes
only the updater, README and optional offline verification log. It does not
package an existing preview, uncommitted source, keys, environment files or
private records. It refuses to overwrite an existing output.

Supported bases are listed in `build-update.py`: the four earlier preview/Ask
Genius versions, remote and verified local layout updates, and the installed
improvements releases `724ca86b0de00c59ade1c8c54fac17ec9bacbc71` and
`5bba1ce0c502c074d481a4b2228091ec5873c72d`. The local-only layout commit retains
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
presence, installed-improvements compatibility, both previous backups'
coexistence, idempotence and rollback. Include the
final test log, not temporary fixtures or private files, in the ZIP. These tests
do not establish real Docker/Mac startup, PostgreSQL migration execution or model
answer quality.

Public share routes are accessible without login, but the Mac preview's
`127.0.0.1` origin is reachable only on that Mac. An incognito window can validate
unauthenticated access locally; sharing across devices requires a reachable
deployed origin. The updater does not expose the local server or alter its
network configuration. Link management and revocation are outside this MVP.
