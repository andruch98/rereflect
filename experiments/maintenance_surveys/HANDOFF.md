# Maintenance-survey integration: updated handoff

## Repository and revision state

- Repository: https://github.com/andruch98/rereflect
- Base: master, 59dfd9122b20d0098eceedf8e1d1296e86b6f0a3.
- Branch: feat/maintenance-survey-integration.
- Previous integration/review tip: 22173b1277e5baf4a3a83cd4014a927eb4cdca98.
- Verified font implementation and evidence commit: 56a5207f2e2a222c799b40e9ce529d1a785399e7.
- The following documentation commit updates this handoff and CHANGED_FILES.txt only. Resolve the branch tip with `git rev-parse feat/maintenance-survey-integration`; its exact hash is reported with this handoff in chat.
- CHANGED_FILES.txt inventories all 85 paths changed against the base, with a purpose for each.
- The previous preview ZIP, Git bundle, patch and Base64 bundle copies are OUTDATED. They describe 22173b1 and do not contain the font change or preserved evidence. They were not regenerated in this task.
- Nothing was pushed, merged, deployed or installed into the Mac preview. No email or live-model calls were made.

## Implementation

The maintenance flow remains: fictional maintenance_completed event -> persisted simulated invitation -> private resident survey -> immutable submitted answers -> authenticated Surveys list/detail -> authorized original-answer evidence in Ask Genius.

Surveys remain separate from reviews. The original maintenance questionnaire, answer choices, rating labels, optional comment limit and version/context snapshots are preserved. Draft resumption, occurrence-specific links, durable deduplication, opt-outs and community permissions remain in place. Survey filtering uses submission time separately from ticket completion; unresolved resident answers remain unresolved evidence. Survey-backed chat sharing stays unavailable. No scheduling, reminder or automatic survey-analysis pipeline was added.

## Focused font change

Only three application files change in this follow-up:

1. services/frontend-web/app/layout.tsx: remove next/font/google imports, font initialization and generated font classes; retain the body/layout structure and antialiasing.
2. services/frontend-web/app/globals.css: remove the Google Fonts CSS import and set system font variables.
3. services/frontend-web/tailwind.config.ts: map existing sans/serif/mono utilities to those variables, overriding the shared font names for this frontend only.

Sans: system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif.
Serif: Georgia, Times New Roman, serif.
Mono: ui-monospace, SFMono-Regular, Menlo, Consolas, Liberation Mono, monospace.

Spacing, widths, size classes, page structure and shared UI/landing configuration were not changed. Font metrics and line wrapping can vary by operating system; pixel-identical text is not promised.

## Build setup and actual new checks

The repository pins pnpm 10.32.1 and documents a root pnpm workspace installation. The environment's default pnpm command was 11.19.0, so this follow-up used Corepack's pinned version. Node was 24.19.0, Next.js 16.1.6 and TypeScript 5.9.3. The frozen lockfile and dependency manifests did not change; there were no dependency upgrades.

An initial offline installation lacked cached pnpm-10 tarballs. A frozen online installation succeeded. It reported ignored optional dependency build scripts; no approval/configuration changes were needed for the build. Corepack's cache was kept under work/ in this environment.

Commands from the repository root:

```bash
corepack pnpm install --frozen-lockfile
corepack pnpm --filter customer-feedback-frontend build
corepack pnpm --filter customer-feedback-frontend lint
corepack pnpm --filter customer-feedback-frontend exec vitest run __tests__/reviews/GeniusMessage.test.tsx __tests__/surveys
corepack pnpm --filter customer-feedback-frontend exec tsc --noEmit --incremental false --pretty false
```

Actual results:

- Production build: PASS, exit 0, using default Turbopack. Compilation, built-in TypeScript validation and generation of all 60 static pages completed.
- ESLint: PASS, exit 0; 0 errors and 42 existing warnings.
- Focused survey/evidence tests: PASS, 30 tests in 2 files.
- Standalone full-project tsc: FAIL, exit 2; 87 existing test diagnostics, with no new diagnostics.
- Production standalone browser: PASS at widths 390 and 1440. Sans, serif and mono computed to the new system stacks; no horizontal overflow, Google Font requests or page errors. The resident API was mocked for this font/layout check; this was not new backend validation.
- git diff --check: PASS.

Build checks used disabled telemetry/Sentry credentials and no model credentials. The browser blocked external requests. No external font download is required by the application now.

### Distinguishing the previous two build failures

The Google Fonts failure was an application dependency: next/font/google fetched font files at build time, and the CSS import also requested Google Fonts in browsers. Both frontend entry points are removed.

The earlier Turbopack failure was an environment setup problem: the isolated source copy had node_modules symlinked outside that copy's filesystem root. This follow-up built in the real repository workspace, where normal pnpm symlinks resolve inside its node_modules/.pnpm store. The default Turbopack build passed without a bundler workaround, TypeScript suppression or changed validation configuration.

The successful build still reports nonfatal existing warnings about the middleware filename convention, old Browserslist data and the shared Tailwind configuration's module type. These were not upgraded or changed.

## The 87 TypeScript diagnostics

All locations below are relative to services/frontend-web. Every diagnostic points to test code, including tests nested under app/ and components/. No application-source diagnostic was found in the current full-project tsc capture.

1. Stale typed fixtures: 75 diagnostics, consisting of 74 AISettings fixture errors and one UserResponse fixture error. Examples:
   - __tests__/settings/AISettingsEmbeddings.test.tsx:94, TS2740: mock settings omit required sentiment/classifier fields.
   - __tests__/settings/AISettingsGeneral.categoryClassifier.test.tsx:73, TS2741: churn_classifier_mode is missing.
   - contexts/__tests__/AuthContext.test.tsx:78, TS2345: mocked user lacks created_at.
2. Incorrect mocked response shape: 1 diagnostic.
   - __tests__/settings/AISettingsProviders.test.tsx:312, TS2322: result is a string, while the API type requires Record<string, unknown>.
3. Browser-location mocks: 5 diagnostics.
   - components/__tests__/OidcSignInButton.test.tsx:26 and app/(dashboard)/settings/integrations/salesforce/__tests__/SalesforcePage.test.tsx:154 restore Location into window.location, whose assignment type is string & Location, producing TS2322. SamlSignInButton, api-client and Salesforce:244 have the same cause.
4. DOM element narrowing: 3 diagnostics.
   - __tests__/settings/NotificationsSettingsPage.test.tsx:170,194,206, TS2345: within() requires HTMLElement, but the helper returns Element.
5. Test-helper typing: 2 diagnostics.
   - __tests__/copilot/actionsContract.test.tsx:49, TS2304: beforeEach has no typed import/global declaration.
   - __tests__/feedbacks/FeedbackDeleteRoleGate.test.tsx:132, TS2493: code indexes a mock-call tuple inferred as empty.
6. Intentionally invalid enum input: 1 diagnostic.
   - lib/api/__tests__/outreach.bulk.test.ts:124, TS2322: the rejection test passes tone 'bossy', outside OutreachTone, without a type-level escape.

These groups total 87. Vitest transpiles TypeScript and executes runtime assertions; it is not a full-project type checker. Its globals:true setting supplies beforeEach at runtime even though standalone tsc lacks that declaration here.

Next.js 16.1.6's built-in runTypeCheck filters diagnostics in __tests__, __mocks__, *.test.* and *.spec.*. This is existing framework behavior, not a new exclusion or bypass. The project's tsconfig still includes its tests. Thus production build success and standalone tsc failure are distinct, accurate results. The repository is not fully clean under standalone tsc; those test issues remain outstanding.

### Preserved master comparison evidence

Committed under experiments/maintenance_surveys/verification/font-build/:

- master-tsc.log: original unchanged-master capture at 59dfd9122b20d0098eceedf8e1d1296e86b6f0a3.
- pre-font-feature-tsc.log: original feature capture before this font change.
- original-comparison.json: original 87-versus-87 comparison record.
- current-tsc.log: newly run standalone tsc output after the font change.
- comparison.json: independently recomputed matching signatures and source-file hashes.
- production-build.log: successful pinned-pnpm production build output.
- browser-font-check.json: production browser font and viewport observations.
- README.md: method, commands, grouped examples and limitations.

The comparison removes only the archived baseline path prefix and compares the full file/line/column/error-code/message strings. All 87 signatures match across the three captures. All 18 diagnostic test files have identical contents at master, the previous feature commit and this follow-up. Original TypeScript logs are preserved without rewriting their diagnostics; only terminal progress whitespace in the production build log was normalized. Master was not rebuilt in this follow-up; its preserved capture was compared again. The 87 issues were not broadly fixed.

## Previous integration verification, retained historical results

These results were reported during the original integration; they were not all rerun for this font-only change:

- Survey API/storage/concurrency: 35 passed, including four PostgreSQL race cases; subsequent offline Ask demo CLI checks: 3 passed.
- Ask Genius offline suite: 180 passed; final selection delta: 20 passed.
- Migration/RBAC checks: 32 passed; worker model parity: 5 passed.
- Full frontend Vitest: 1,970 passed, 1 existing skipped.
- Updater checks: 9 passed; exact-commit builder checks: 7 passed.
- PostgreSQL clean migration and preservation/round-trip checks passed with authentication, saved review analysis and chat sentinels intact. Single migration head: f2e8463ab154.
- Chromium checked draft reload, persisted submission, dashboard answers, source-aware evidence navigation and blocked sharing. Models/providers were mocked.

The full backend/worker suites, full Docker Compose startup, installed Mac preview, real Resend operation and live-model answer quality remain unverified. The new successful frontend build does not establish those behaviors.

## Outstanding issues and deferred work

Intentionally unchanged:

- The starter 'How many survey responses did we receive during this period?' does not match strict local count grammar and returns a limitation. 'How many completed maintenance surveys?' is a supported record-count phrasing.
- General AppSidebar uses the customers detail-path prefix for Surveys active state. Survey detail highlighting can be missing; customer detail pages can incorrectly highlight Surveys too.
- The 87 test TypeScript diagnostics and 42 lint warnings remain.
- Platform system fonts can change text wrapping.
- Timing, reminders/quiet hours, automatic survey analysis/classification, other survey types, wording/visual refinement and approved survey sharing remain deferred. SMS/PMS connections, public-review solicitation, management responses, deployment and a client trial remain outside this increment.

## Exact database-preserving local-preview instructions

These are future operator instructions, not actions performed on the Mac in this task. They require a FULL checkout containing this font follow-up. The old bundle and ZIP cannot provide it. Once the current branch has been transferred separately, verify its revision before use:

```bash
git switch feat/maintenance-survey-integration
git log -3 --oneline
git status --short
```

### Separate fictional preview

Run from the current full checkout with Docker Desktop running:

```bash
docker compose -f experiments/maintenance_surveys/compose.yml up -d --build
docker compose -f experiments/maintenance_surveys/compose.yml logs --tail=40 api
docker compose -f experiments/maintenance_surveys/compose.yml exec -T api python -m src.survey_demo simulate survey-demo-fixtures/maintenance-completed.json
docker compose -f experiments/maintenance_surveys/compose.yml exec -T api python -m src.survey_demo inspect fictional-maintenance-event-001
SURVEY_URL="$(docker compose -f experiments/maintenance_surveys/compose.yml exec -T api python -m src.survey_demo link fictional-maintenance-event-001)"
open "$SURVEY_URL"
open http://127.0.0.1:53104/surveys
```

This uses a separate boomsay-survey-demo project/database volume and ports 53104/53105. The fictional login is manager@survey-demo.invalid / fictional-survey-demo-login. Never reuse these published demo settings for real data or point its initializer at an existing preview database.

Select 2 Bad, No still unresolved, Not sure and an optional comment; save a draft, reload and submit. Then inspect View answers. Ask verification uses actual application records/routes with a mocked model:

```bash
docker compose -f experiments/maintenance_surveys/compose.yml exec -T api python -m src.survey_demo verify-ask
open http://127.0.0.1:53104/ask-genius
```

Open [OFFLINE MOCK] Survey verification in history. The normal demo composer remains disabled; no paid model is configured. Restart with `docker compose -f experiments/maintenance_surveys/compose.yml restart api`; stop with the same command ending in `stop`. Neither command deletes its database volume.

### Existing Mac preview

Build a NEW updater from the latest clean full checkout. Choose unused ZIP/extraction names; the builder refuses to overwrite an existing ZIP:

```bash
FEATURE_COMMIT="$(git rev-parse feat/maintenance-survey-integration)"
python3 experiments/maintenance_surveys/preview_updates/build-update.py --commit "$FEATURE_COMMIT" --output "$HOME/Downloads/boomsay-survey-font-update.zip"
mkdir "$HOME/Downloads/boomsay-survey-font-update"
python3 -m zipfile -e "$HOME/Downloads/boomsay-survey-font-update.zip" "$HOME/Downloads/boomsay-survey-font-update"
cd "$HOME/Downloads/boomsay-dashboard-preview"
python3 "$HOME/Downloads/boomsay-survey-font-update/boomsay-maintenance-survey-update/update-preview.py"
bash start-local.sh
open http://127.0.0.1:53004/surveys
```

The preview folder/port are historical documented values, not a new inspection of the Mac. The updater checks supported source releases, manifests/archive checksums and known startup hashes before writes. It preserves the database volume, Compose/network settings, startup scripts, credentials/login, AI configuration, saved reviews/analysis, preferences and chat history. Normal startup applies additive migrations to the existing database. No reset or automatic survey-analysis backfill is required.

Keep backup-before-maintenance-survey-update and earlier backups. The backup contains source/metadata, not a database backup. After migration, restoring older source alone is unsupported because its migration tree lacks the recorded revision. On rejection/startup failure, retain the installation, errors and backups for recovery; do not force checksums, reset/restamp/drop the database, remove volumes, rerun a fresh installer or recreate credentials. Never use down -v as an installation step.
