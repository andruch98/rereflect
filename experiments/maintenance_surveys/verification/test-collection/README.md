# Combined migration-test collection fix

Verified 3 November 2026 against the correction branch starting at
f4c6c222097e1c5a3d7078018da8426695d6cc07.

## Failure and narrow correction

GitHub run [41737874283](https://github.com/andruch98/rereflect/actions/runs/41737874283)
passed the frontend, worker, clean database upgrade and single migration-head
checks. Backend pytest collected 5,687 items plus one error and stopped before
executing tests: `ask_genius_offline/test_migration.py` and
`surveys_offline/test_migration.py` both imported as `test_migration`.

Rename only the survey module to `test_survey_migration.py`. Preserve every byte
of its contents, the existing pytest configuration and historical test logs.
Update the changed-file inventory and current handoff. No application, database,
prompt, runtime configuration or workflow changes are included.

## Bounded local replay

Run from `services/backend-api`, using the existing Python 3.12 test environment:

```sh
python -m pytest --noconftest tests/ask_genius_offline/test_migration.py tests/surveys_offline/test_migration.py -q
```

Before: collection failed with `import file mismatch`, exit 2. The error matched
GitHub. After the rename, run the same command using the survey test's new path:

```sh
python -m pytest --noconftest tests/ask_genius_offline/test_migration.py tests/surveys_offline/test_survey_migration.py -q
```

After: three tests passed, exit 0; one existing SQLAlchemy deprecation warning.
These migration tests need no fixtures. `--noconftest` avoids unrelated local
application integrations; it is a focused reproduction, not a full-suite pass.
GitHub reruns the unchanged full workflow and normal test fixtures separately.

The tests use fictional SQLite records to check historical user/chat preservation
and survey schema upgrade/downgrade. No model or email request is made; model
inputs/outputs, token usage and cost are not applicable. Complete local output
and GitHub results are retained in the downloadable verification record.

Stop criteria: the existing combined GitHub checks pass, or a new blocker is
reported to Andres before expanding scope. No merge or deployment is authorized.
Frontend tests/lint do not establish a successful production build; earlier
production TypeScript issues remain outside this correction.
