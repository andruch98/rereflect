# System-font build and TypeScript evidence

Font follow-up on `feat/maintenance-survey-integration`, after
`22173b1277e5baf4a3a83cd4014a927eb4cdca98`. Only three application files change:
frontend root layout, frontend global CSS, and frontend Tailwind font-family
mapping. Shared UI/landing typography, layout dimensions, dependency versions,
TypeScript configuration and Next build validation settings are unchanged.

## Current checks

- Pinned pnpm 10.32.1 via Corepack; frozen lockfile installation from monorepo root.
- Next 16.1.6, TypeScript 5.9.3, Node 24.19.0; no dependency upgrades.
- `corepack pnpm --filter customer-feedback-frontend build`: exit 0, default
  Turbopack, compilation and TypeScript check passed, 60 static pages generated.
- `corepack pnpm --filter customer-feedback-frontend lint`: exit 0; 0 errors,
  42 existing warnings.
- `corepack pnpm --filter customer-feedback-frontend exec vitest run __tests__/reviews/GeniusMessage.test.tsx __tests__/surveys`:
  30 tests passed in 2 files.
- `corepack pnpm --filter customer-feedback-frontend exec tsc --noEmit --incremental false --pretty false`:
  exit 2; exactly 87 existing test diagnostics, identical to both captures below.
- Production standalone Chromium check: widths 390 and 1440, system sans/serif/mono
  computed correctly, no horizontal overflow, no Google Font requests or page
  errors. Resident API response mocked; this checks fonts/layout, not the backend.

Builds used disabled telemetry/Sentry credentials and no model credentials. No
emails, live models, deployment, Mac preview installation or database changes.
The old isolated-copy Turbopack error concerned node_modules pointing outside that
copy. The real workspace has normal pnpm links into its own node_modules/.pnpm;
the default production build now passes with no bundler/configuration workaround.
An initial offline install found no pnpm-10 cached tarball; frozen online install
succeeded. pnpm reported ignored optional package build scripts; no approval or
package changes were needed for the successful build.

## Preserved baseline

- `master-tsc.log`: original unchanged-master capture at
  `59dfd9122b20d0098eceedf8e1d1296e86b6f0a3`, made during the integration.
- `pre-font-feature-tsc.log`: original feature capture, before this font change.
- `original-comparison.json`: original 87-versus-87 comparison record.
- `current-tsc.log`: newly run full-project tsc diagnostic output.
- `comparison.json`: recomputed match of all 87 file/line/column/code/message
  signatures across the three captures, plus hashes of all 18 diagnostic test
  files, identical at master, pre-font feature and current source.
- `production-build.log`: successful pinned-pnpm default production build; terminal
  progress whitespace normalized, original retained in work/font-production-build-pinned.log.
- `browser-font-check.json`: computed font stacks and viewport checks.

Normalization removes only `work/frontend-baseline/services/frontend-web/` from
baseline diagnostic paths. All original multiline logs are retained. Test files
are unchanged; no tests, compiler exclusions or validation checks were repaired or
suppressed to obtain these results. Unchanged master was not rebuilt in this
follow-up; its earlier capture is preserved and independently compared again.

## Why a production build passes while tsc reports 87 errors

Next 16.1.6's built-in `dist/lib/typescript/runTypeCheck.js` filters diagnostics in
`__tests__`, `__mocks__`, `*.test.*` and `*.spec.*` files. That is the installed
framework's default behavior, not a configuration change here. Our tsconfig still
includes all TS/TSX files, so standalone `tsc` reports test diagnostics. Vitest uses
transpilation and runtime assertions rather than a full TypeScript check; its
`globals: true` also supplies beforeEach at runtime.

All 87 diagnostics affect tests, including tests under app/components directories.
Grouped by cause (paths below relative to services/frontend-web):

1. Stale typed fixtures: 75 diagnostics (74 AISettings, 1 UserResponse).
   `__tests__/settings/AISettingsEmbeddings.test.tsx:94` is TS2740: mock settings
   lack sentiment/classifier fields. `__tests__/settings/AISettingsGeneral.categoryClassifier.test.tsx:73`
   is TS2741: churn_classifier_mode missing. `contexts/__tests__/AuthContext.test.tsx:78`
   is TS2345: mocked user lacks created_at.
2. Mock response shape: 1 diagnostic. `__tests__/settings/AISettingsProviders.test.tsx:312`
   is TS2322: result is a string, API type requires Record<string, unknown>.
3. DOM location mocks: 5 diagnostics. `components/__tests__/OidcSignInButton.test.tsx:26`
   and `app/(dashboard)/settings/integrations/salesforce/__tests__/SalesforcePage.test.tsx:154`
   restore Location to window.location; current DOM typings require string & Location
   at those assignments (TS2322). SamlSignInButton, api-client and Salesforce:244
   have the same cause.
4. DOM element narrowing: 3 diagnostics. `__tests__/settings/NotificationsSettingsPage.test.tsx:170,194,206`
   passes Element to within(), which requires HTMLElement (TS2345).
5. Test-helper typings: 2 diagnostics. `__tests__/copilot/actionsContract.test.tsx:49`
   uses beforeEach without a typed import/global declaration (TS2304).
   `__tests__/feedbacks/FeedbackDeleteRoleGate.test.tsx:132` indexes an inferred
   empty mock-call tuple (TS2493).
6. Intentionally invalid enum fixture: 1 diagnostic.
   `lib/api/__tests__/outreach.bulk.test.ts:124` passes tone bossy to an OutreachTone
   parameter to test API rejection, without a type-level escape (TS2322).

These total 87; no application-source diagnostics were found in the current tsc
capture. Test fixture issues can affect future strict test type-checking even
though runtime tests passed. They are not broadly fixed in this task.

## Still outstanding, intentionally not fixed

- Survey count starter “How many survey responses did we receive during this
  period?” is outside the strict local count grammar; it returns a limitation.
- General AppSidebar uses the customers detail prefix in the Surveys active-state
  branch, so survey detail highlighting may be absent and customer detail
  highlighting may incorrectly include Surveys.
- Future timing/reminders, survey analysis, other templates and visual refinement
  remain deferred. System fonts can vary by platform and change line wrapping;
  existing layout structure, spacing and size classes were retained.
