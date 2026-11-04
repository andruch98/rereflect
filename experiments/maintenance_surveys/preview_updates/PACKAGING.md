# Maintenance survey preview update

The dedicated updater selectively follows the existing Ask Genius source update
protocol. It uses `backup-before-genius-answer-recovery-update`, retains existing
supported base commits plus the published survey base ccb53d4122a76ffd6045d2bf188d20dfdb712d2d and verified master `59dfd9122b20d0098eceedf8e1d1296e86b6f0a3`,
plus the installed continuity update `6dd7827360d1a370d59537a0c7407bf5ad5faeff`,
and retains the two approved startup-script hashes. It does not alter startup,
Compose, networks, credentials, AI configuration or database storage. The two
recognized starters already run `python -m alembic upgrade head` before API startup.

After committing the reviewed feature locally, package that exact commit:

```sh
python3 experiments/maintenance_surveys/preview_updates/build-update.py \
  --commit FULL_40_CHARACTER_FEATURE_COMMIT \
  --output /absolute/path/boomsay-answer-recovery-update.zip \
  --verification-log /absolute/path/offline-checks.txt
```

The builder checks its scripts and README match the selected commit, runs
`git archive` on the existing application allowlist, verifies required survey and
prior Ask Genius files, and records the commit plus archive SHA-256. The simulation
command lives under `services/backend-api/src` so the preview archive includes it.
The ZIP's `handoff/` directory includes the integration guide, final handoff and
fictional event/answer fixtures, read with `git show` from that exact commit. A
committed `experiments/maintenance_surveys/CHANGED_FILES.txt`, when present, is
included as `handoff/CHANGED_FILES.txt`. Original document names and relative links
are preserved, including `handoff/README.md` and the updater instructions under
`handoff/preview_updates/`. Missing required committed documentation
is a packaging error; uncommitted local documents cannot silently substitute.
Archives, manifests and verification logs are deliverables outside Git. No local
preview, uncommitted source, private data or environment files are packaged.

The separate demo Compose files remain in the full feature checkout. An existing
preview's source-only `app/` directory and this update ZIP do not contain a full
repository and cannot be used as that demo's working directory.

```sh
python3 experiments/maintenance_surveys/preview_updates/verification/test_update.py
python3 experiments/maintenance_surveys/preview_updates/verification/test_build.py
```

Tests use generated public skeleton files and fictional private sentinels. Their
success verifies file preservation, validation, failure rollback, safe extraction,
required migration presence, exact-commit packaging and repeat-update behavior.
The real installed preview skeleton is unavailable here, so synthetic tests do not
establish actual Mac/Docker startup or compatibility with an unknown installation.
No database is connected or changed by the updater or these packaging tests.
