# Maintenance surveys: implementation and verification handoff

Implemented in `andruch98/rereflect`, local branch
`feat/maintenance-survey-integration`, from verified `master` commit
`59dfd9122b20d0098eceedf8e1d1296e86b6f0a3`. Run `git rev-parse HEAD` for the
final local feature commit. Nothing was pushed, opened as a PR, merged or deployed.
The installed Mac preview was not accessed or changed.

The read-only source was `andruch98/boomsay-agent/main` at verified commit
`9af23a3811615d08cb4067c293ef81da23b35887`; its checkout remains unchanged.
ReReflect PR #5 was verified open and unmerged, with its backend, frontend and
worker check runs all completed successfully at head `6deaa21a34d1a1a2919ca40e0c04861879e5e6c4`.
The new migration naturally moves
the expected single head to `f2e8463ab154`; the historical chat migration test now
checks ancestry. No separate duplicate migration-head fix or PR merge was added.

The exact changed-file inventory is in [CHANGED_FILES.txt](CHANGED_FILES.txt).
The [integration guide](README.md) contains the complete commands and record map;
the [Mac source updater](preview_updates/README.txt) preserves private settings and
database storage and starts no services itself.

## Implemented flow

1. A generic, timezone-qualified `maintenance_completed` fictional event enters
   the application's ingestion service, through either the guarded demo CLI or
   an admin/owner simulation endpoint.
2. Community-scoped resident/unit identities, immutable maintenance occurrence
   context, a private survey instance and one invitation are persisted together.
   Database uniqueness and PostgreSQL locking preserve one link per occurrence.
3. The invitation uses real preparation and persistence, with a fake sender at
   the provider boundary. Its outcome is explicitly `simulated`, never sent or
   delivered. The separate Resend adapter reuses the application's transport;
   there is no live-send route or CLI mode. Resident and invited-email opt-outs
   remain durable across contact/identity changes.
4. `/survey/{token}` loads the original four maintenance questions without a
   manager login. Drafts persist; final submission validates the frozen question
   snapshot. Completed answers survive retries, late drafts and concurrent writes.
5. `/surveys` and `/surveys/{public_id}` use existing manager authentication and
   community permissions to show unfinished/completed instances, simulated
   invitations, context and original readable answers.
6. Ask Genius retrieves finalized originals with question text, options and
   rating labels. Periods filter survey submission time in America/New_York,
   independently of ticket completion. Application records calculate submission,
   distinct-resident and resolution counts. Original evidence opens authenticated
   `/surveys/{UUID}` detail. Survey-backed chats cannot be publicly shared.

The source catalog is preserved exactly, including `Not sure`, required rules,
rating labels and the optional 2,000-character comment. Each instance stores
catalog/template version, unrendered and rendered questions, choices and context.
Survey tables are separate from review `feedback_items`. No scheduler, reminder,
automatic analysis job, survey sentiment/topic assignment or saved summary exists.
Ask Genius can summarize original answers on demand using the existing AI seam;
it explains unavailable saved survey analysis rather than inventing it.

## Local use, with fictional data only

Use a complete checkout of this feature branch and Docker Desktop. These commands
create the separate `boomsay-survey-demo` project and its own database volume;
they do not install over `~/Downloads/boomsay-dashboard-preview`.

```bash
docker compose -f experiments/maintenance_surveys/compose.yml up -d --build
docker compose -f experiments/maintenance_surveys/compose.yml logs --tail=40 api

docker compose -f experiments/maintenance_surveys/compose.yml exec -T api \
  python -m src.survey_demo simulate survey-demo-fixtures/maintenance-completed.json
docker compose -f experiments/maintenance_surveys/compose.yml exec -T api \
  python -m src.survey_demo inspect fictional-maintenance-event-001

SURVEY_URL="$(docker compose -f experiments/maintenance_surveys/compose.yml exec -T api \
  python -m src.survey_demo link fictional-maintenance-event-001)"
open "$SURVEY_URL"
open http://127.0.0.1:53104/surveys
```

The demo starts by applying additive migrations and initializing its own empty
database. Initialization refuses a foreign community/database and retains its
existing login on repeat. The fictional manager is `manager@survey-demo.invalid`,
password `fictional-survey-demo-login`. No keys or credentials are borrowed from
the environment or an existing preview. Do not use these published settings for
real data or a shared installation.

Choose `2 Bad`, `No, still unresolved`, `Not sure`, and an optional comment; save
a draft, reload and submit. The developer alternative uses the actual public
submission route, never a direct completed-answer database insert:

```bash
SURVEY_TOKEN="${SURVEY_URL##*/}"
curl --fail-with-body -X POST \
  -H 'Content-Type: application/json' -H 'Origin: http://127.0.0.1:53104' \
  --data-binary @experiments/maintenance_surveys/fixtures/unresolved-answers.json \
  "http://127.0.0.1:53105/api/v1/resident-surveys/$SURVEY_TOKEN/submit"
```

Inspect the submitted row using **View answers** in `/surveys`. Repeating simulate
returns its existing invitation/link; another event/occurrence gets its own link.
The integration guide includes a second-occurrence example and restart commands.

Ask Genius's normal demo composer remains disabled because no live model is
configured. The developer `verify-ask` command described in the integration guide
exercises actual Ask Genius routes/history with an explicitly mocked model, without
persisting provider configuration. Open `/ask-genius` to inspect that saved demo
chat and its original-answer links. Mocked tests establish integration behavior,
not live AI quality. Existing installed-preview AI configuration is left intact;
no paid model evaluation was run or enabled for this task.

```bash
docker compose -f experiments/maintenance_surveys/compose.yml exec -T api \
  python -m src.survey_demo verify-ask
open http://127.0.0.1:53104/ask-genius
```

Select **[OFFLINE MOCK] Survey verification** in saved history. Its count and
unresolved answers use application calculations; the narrative and original-answer
follow-up are clearly marked mocked outputs. The command prints the conversation
ID and checks its survey evidence URLs against authenticated original-answer
routes. The normal demo composer stays disabled, and no provider setting changes.

For the existing Mac preview, only after choosing to install the packaged update:

```bash
cd "$HOME/Downloads/boomsay-dashboard-preview"
python3 ../boomsay-maintenance-survey-update/update-preview.py
bash start-local.sh
open http://127.0.0.1:53004/surveys
```

These are the documented known preview layout/port, not a fresh inspection of the
Mac. The updater checks recognized source releases, manifest/archive checksums and
startup hashes before writing. It preserves Compose, startup scripts, credentials,
review analysis, preferences and chat history; normal startup runs Alembic upgrade
head. Keep backups after migration. Never reset, restamp, drop the database or
remove volumes as an installation or rollback step.

## Verification actually performed

All identities and storage were isolated and fictional. Email HTTP/job boundaries
were blocked or mocked; model responses were mocked. No Resend, SMS, external PMS
or paid model calls were made. Tests required a socket-enabled execution sandbox
because FastAPI TestClient uses socket pairs; an initial restricted-sandbox attempt
hung and was terminated, then passed with the appropriate sandbox capability.

Commands below are from their indicated service directories, using the isolated
`work/venv` created for this task. Equivalent installed service virtualenvs work.

| Command/check | Actual result |
| --- | --- |
| Backend: `TEST_SURVEY_POSTGRES_URL=postgresql://postgres:survey-test-only@127.0.0.1:55432/survey_test ../../work/venv/bin/pytest --confcutdir=tests/surveys_offline tests/surveys_offline -q --timeout=30` | 35 passed, including four PostgreSQL concurrent replay/submission/draft cases. |
| Backend: `../../work/venv/bin/pytest --confcutdir=tests/surveys_offline tests/surveys_offline/test_demo_verify_ask.py -q --timeout=30` | 3 additional offline handoff checks passed after adding `verify-ask`: actual ingestion/submission/chat routes, mocked outputs and configuration restoration, refusal of drafts/foreign storage. |
| Backend: `../../work/venv/bin/pytest --confcutdir=tests/ask_genius_offline tests/ask_genius_offline -q --timeout=30` | 180 passed; after the final small selection correction, all 20 survey Ask tests passed again. |
| Backend: `PATH=/workspace/rereflect/work/venv/bin:$PATH ../../work/venv/bin/pytest --noconftest tests/test_outreach_migration.py tests/test_mutation_route_rbac_sweep.py -q --timeout=30` | 32 passed. |
| Worker: `../../work/venv/bin/pytest --noconftest tests/test_model_parity_classifier.py -q --timeout=30` | 5 passed. Review date, rating, saved analysis, text, source and community types also matched between actual backend/worker models. Survey tables need no worker mirror because no worker consumes them. |
| Frontend: `node_modules/.bin/vitest run` | 1,970 passed, 1 pre-existing skipped; 222 test files passed, 1 skipped. |
| Frontend: `node_modules/.bin/vitest run __tests__/reviews/GeniusMessage.test.tsx __tests__/surveys` | 30 passed after a small duplicate-evidence-text cleanup. |
| Frontend: `node_modules/.bin/eslint .` | Passed, 0 errors and 42 existing warnings. |
| Frontend: `node_modules/.bin/tsc --noEmit` | Failed on 87 existing test-fixture errors; an archived clean master had exactly the same 87 error signatures, with zero feature-only errors. |
| Frontend: production `next build` | Isolated Turbopack snapshot rejected an external dependency symlink; webpack fallback failed fetching existing Google Fonts through the environment proxy. Production build remains unverified. |
| `python3 experiments/maintenance_surveys/preview_updates/verification/test_update.py` | 9 passed: synthetic preview preservation, checksums, idempotence and rollback. |
| `python3 experiments/maintenance_surveys/preview_updates/verification/test_build.py` | 7 passed: exact-commit package checks; actual final archive was built separately after local commit. |
| `docker compose -f experiments/maintenance_surveys/compose.yml config --quiet` | Passed. Full Compose image build/start was not run. |
| `git diff --check` and scoped Python compile checks | Passed. |

Real PostgreSQL 16 checks migrated a fresh database through the final head and
separately migrated another database to the previous head, inserted actual ORM
authentication/review-analysis/chat sentinels, upgraded, checked every existing
field and the six survey-table schemas, downgraded and upgraded again. Existing
records remained unchanged throughout. Migration startup initially required the
repository's synthetic Fernet test key; with that test configuration the full
chain passed. Alembic reports exactly one final head, `f2e8463ab154`.

Headless Chromium inspected the Next.js form at 390px mobile width, draft reload,
persisted confirmation after reload, dashboard detail and Ask Genius evidence
navigation. The backend scaffold mounted the actual feature routes, actual JWT
authentication dependency and PostgreSQL storage, with small identity/community
read stubs and a fake model. It did not test the full main-app startup or real
login/provider integrations. No browser page errors occurred. Existing fonts used
fallbacks because remote font downloads were unavailable.

Readable browser input: fictional Jamie Example, unit 204, ticket `DEMO-WO-1001`,
maintenance marked completed `2026-11-01T10:15:00-05:00`; rating `2`, resolution
`unresolved`, response time `not_sure`, comment “The sink still leaks after the
completed ticket. Please check the seal again.” The actual browser answer was:

> 1 submitted maintenance survey(s) from 1 distinct resident(s) report that the
> issue is still unresolved in All available history. Ticket completion does not
> change the resident’s reported resolution status.

Actual evidence href:
`/surveys/898d2883-c5bb-47af-82ff-e8a64014da25`. Clicking it opened the original
questions with `2 — Bad`, `No, still unresolved`, `Not sure` and the original
comment. The **Share** menu action was disabled. This is an isolated test UUID,
not a fixture identifier that will recur in a fresh demo.

Full backend/worker suites were not run; bounded feature, review/chat regression,
schema, concurrency and full frontend checks were used instead. The installed Mac
preview, full Docker Compose startup, live Resend operation, live AI quality and
real personnel/PMS integrations remain unverified. The Mac updater tests use
synthetic skeletons, not the user's installed preview.

## Remaining work

Deferred as approved: 24-hour invitation timing from ticket completion, one
reminder 24 hours after provider acceptance, 9 a.m.–6 p.m. property windows,
automatic survey analysis/classification, other survey types, wording and visual
refinement, real delivery/provider operational handling and approved survey-sharing
behavior. SMS, PMS connections, public-review solicitation, management responses,
hosting, deployment and a client trial remain outside this increment.
