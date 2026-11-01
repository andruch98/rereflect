# BoomSay maintenance surveys — final update handoff

## Result and revision

The complete initial maintenance-survey flow worked in the full application with
fictional data and mocked email/model responses. The general sidebar now marks
Surveys on list/detail routes and leaves it inactive on customer routes.

- Repository: andruch98/rereflect.
- Branch: feat/maintenance-survey-integration.
- Original master base: 59dfd9122b20d0098eceedf8e1d1296e86b6f0a3.
- Starting checkout: b1fe329596620dbdba11cc28171103ed546876c4, clean.
- Verified implementation/evidence: 6306996ff6ae3df98d58f087d7c0f2dddffaeb33.
- The subsequent documentation-only commit is the final package commit. Its SHA
  is recorded in the delivered filenames, update.json, bundle ref and chat receipt.
- CHANGED_FILES.txt is the complete inventory against the original base.
- Nothing was pushed, merged, deployed or installed into the Mac preview.

## Changes in this pass

1. One sidebar expression now uses each item's own href for detail-route matching.
   Existing navigation, groups and visual design are preserved.
2. The demo manager uses manager@survey-demo.example.com because .invalid is
   rejected by the real login validator. Authentication validation is unchanged;
   no existing manager account or credentials were rewritten.
3. Frontend Docker COPY gives public assets the same nextjs ownership as its
   other assets, fixing non-root startup on the tested build context.
4. Added reproducible full-stack verification with a test-only HTTP model mock,
   real main API/auth/database, production frontend and actual idle Celery worker.

The system-font fix remains intact. Survey questionnaire wording/options,
occurrence links, snapshots, drafts, immutable completion, opt-outs, authorization,
review separation and public-sharing restrictions are preserved. No count-wording
fix, scheduler, reminder, analysis job, other survey type or visual redesign was added.

## Verification

See VERIFICATION.txt for the step-by-step actual results and resolved retries.
The full stack was not a route scaffold: it used src.api.main:app and real
email/password login. The existing BoomSay preview startup flags skipped unrelated
seed/model jobs. Only invitation delivery and the model-provider HTTP boundary
were mocked. The model received the actual finalized four questions and answers.

Passed: event ingestion; immediate simulated invitation; replay deduplication;
public form draft/reload/submit; dashboard status; original questions/labels;
Ask Genius list/narrative/follow-up; evidence navigation; blocked public sharing;
anonymous access denial; API restart and fictional prior-data preservation.
Database totals were one occurrence, survey, invitation and submission. Worker
received no tasks; queue length was zero. No live email or model call occurred.

New checks: production build passed with default Turbopack and 60 static pages;
42 focused frontend tests and 7 backend demo checks passed; lint had 0 errors and
42 existing warnings. Standalone tsc still returns the same 87 test diagnostics,
with no additions. No validation was suppressed. Prior baseline evidence is
preserved; the full unrelated suites were not rerun.

Resolved during testing: invalid fictional manager address, Docker public-asset
ownership, test-network port exposure, lowercase proxy exclusions, and managed
Docker disk exhaustion. Database volumes were retained throughout. The completed
flow used the same submission after the mock-provider retry, without resetting it.

## Remaining limits

- The survey-count starter 'How many survey responses did we receive during this
  period?' remains unsupported. Use the supported wording below.
- The 87 TypeScript test-fixture errors and 42 lint warnings remain for later.
- Live AI answer quality and real email/PMS operation were not evaluated.
- Mac preview installation/startup and ARM builds remain unverified.
- Timing, reminders/quiet hours, automatic survey analysis/classification, other
  survey types, wording/visual refinement and approved survey sharing are deferred.
- The earlier ZIP/bundle are outdated. Use only the newly generated artifacts
  whose filename and metadata match the final commit in the delivery receipt.

## Fresh artifacts

The preview-update ZIP is produced by the existing exact-commit build-update.py.
It contains committed application source, its checksum/commit manifest, updater,
handoff, fixtures and verification report. It contains no private preview data,
credentials or uncommitted code. Its source-only updater preserves the established
preview process.

The Git bundle includes the feature branch and original master/base history, with
no prerequisite repository required. Bundle heads, import into an empty repository,
base ancestry, commit identity, object integrity and changed paths are checked.
Text copies HANDOFF.txt and VERIFICATION.txt accompany the package. Full text is
also pasted in chat because download access in the user's client is not assumed.

## Get a clean full checkout on the Mac

Download/export the fresh bundle identified in the delivery receipt. From its
folder, substitute the real commit suffix in the filename:

```bash
git clone --branch feat/maintenance-survey-integration ./maintenance-survey-feature-COMMIT.bundle boomsay-survey-final-source
cd boomsay-survey-final-source
git log -2 --oneline
git status --short
```

Confirm the full HEAD matches the receipt before continuing. Do not use the older
bundle; it does not contain these changes. No source branch has been pushed online.

## Simple isolated Mac walkthrough — no live provider calls

Run from that complete checkout, with Docker Desktop. Use a new project name to
preserve older isolated demos, including ones with the old .invalid manager.

```bash
compose=(docker compose -p boomsay-survey-final-test -f experiments/maintenance_surveys/compose.yml -f experiments/maintenance_surveys/verification/full-stack/compose.mock.yml)
"${compose[@]}" build api web worker
"${compose[@]}" up -d --no-build
"${compose[@]}" logs --tail=30 api web worker
"${compose[@]}" exec -T api python -m src.survey_demo simulate survey-demo-fixtures/maintenance-completed.json
"${compose[@]}" exec -T api python -m src.survey_demo inspect fictional-maintenance-event-001
SURVEY_URL="$("${compose[@]}" exec -T api python -m src.survey_demo link fictional-maintenance-event-001)"
open "$SURVEY_URL"
```

The source build can take several minutes. This is a separate PostgreSQL volume,
Redis, API, web, idle worker and mock endpoint. Published web/API/model ports are
loopback-only 53204/53205/53206. No real model/email keys are loaded.

1. Select 2 Bad, No still unresolved, Not sure and an optional comment. Let the
   draft save, reload, then submit and wait for confirmation.
2. Open http://127.0.0.1:53204/surveys. Sign in as
   manager@survey-demo.example.com / fictional-survey-demo-login.
3. Confirm resident Jamie Example, unit 204, ticket DEMO-WO-1001, simulated
   invitation status and submission date. Choose View answers and inspect all
   four original questions and readable answers.
4. Open /ask-genius, select All available history, and ask:
   - Show the completed maintenance surveys for this period.
   - What did residents say about their maintenance experience?
   - Show the original answers behind that.
5. The narrative is explicitly MOCKED MODEL output. Follow View original answers
   to the same submission. Ticket completion must not erase its unresolved answer.
6. Repeat simulate: it must retain the survey/link. Restart only the API and
   reopen the submission to check persistence:

```bash
"${compose[@]}" restart api
"${compose[@]}" stop
```

Stop preserves storage. Never use down -v or run the demo initializer against the
installed preview database. These published fictional credentials are for this
isolated local test only. The ordinary demo without this overlay keeps its normal
AI composer disabled; the overlay is what supplies a local HTTP model mock.

## Update the existing Mac preview without resetting data

This optional installation was NOT performed here. First keep the old preview
folder and all existing backups. Unzip the fresh update package into a new folder
beside the existing preview; do not replace private configuration or the database.
The folder/port below are historical documented values, not a new Mac inspection.

For example, if the fresh ZIP is in Downloads, choose an unused extraction folder:

```bash
mkdir "$HOME/Downloads/boomsay-survey-final-update"
python3 -m zipfile -e "$HOME/Downloads/boomsay-maintenance-survey-update-COMMIT.zip" "$HOME/Downloads/boomsay-survey-final-update"
cd "$HOME/Downloads/boomsay-dashboard-preview"
python3 "$HOME/Downloads/boomsay-survey-final-update/boomsay-maintenance-survey-update/update-preview.py"
bash start-local.sh
open http://127.0.0.1:53004/surveys
```

Substitute the exact fresh ZIP filename from the receipt. The updater validates
supported source releases, archive/manifest checksums and known startup hashes
before writes. It changes source/archive metadata and preserves database volume,
Compose/network/startup files, credentials/login, AI settings, reviews/saved
analysis, preferences and Ask Genius history. Normal startup applies additive
migrations to the existing database; no reset or analysis backfill is needed.

Verify the existing login, one original review with saved analysis, an existing
chat and AI connection status. Do not send a live-model question merely to test
installation; use the separate mocked stack for the walkthrough above.

Keep backup-before-maintenance-survey-update and older backups. The backup is
source/metadata, not a database backup. After migration, restoring old source alone
is unsupported. On rejection/startup failure, keep the installation, error and
backups for recovery. Do not force checksums, reset/restamp/drop the database,
remove volumes, recreate credentials or rerun a fresh installer.
