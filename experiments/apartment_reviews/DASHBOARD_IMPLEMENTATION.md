# BoomSay review inbox — first implementation

This is the first dashboard increment, not the completed BoomSay MVP. Base:
`1bcc4aa5a013f2fa9e3d91fab65b79440160b639`, in `andruch98/rereflect`.
BoomSay remains a read-only reference at `9af23a3811615d08cb4067c293ef81da23b35887`.

## Implemented

- Opt-in Reviews inbox and detail routes using the existing shared table and UI components.
- Original text, numeric star rating, rating-only state, source, overall sentiment and saved-analysis method.
- Search, all five sentiment filters, server-side sorting and pagination.
- Saved apartment topics and quotations grouped by each quotation's own saved sentiment.
- Read only `apartment_analysis.final_result`; never substitute raw/rejected AI candidates or reinterpret results.
- Missing analysis, unavailable payloads and keyword fallback stay distinguishable.
- Account-specific query caches; existing API organization authorization retained.
- Original list/detail screens preserved byte-for-byte as `LegacyFeedbackPage.tsx` beside each route.
- Preview list/detail contains no import, edit, delete, generation or re-analysis actions.

Set `NEXT_PUBLIC_BOOMSAY_REVIEW_PREVIEW=true` **at frontend build/start time**
in a separate test installation to select the new list/detail screens. It is off
by default. No environment, running installation, database or deployment was changed.
The flag also selects a Reviews-only navigation shell and BoomSay sign-in screen.
Other dashboard routes redirect to Reviews. Existing upstream screens remain in the
code, behind the default mode. Supplied BoomSay SVGs are preserved unchanged;
the fork favicon is BoomSay in both modes. Original license notices remain intact.

## Data ownership

| Display | Existing source | Rule |
|---|---|---|
| Review text | `FeedbackItem.text` | Preserve original text; blank is explicitly labeled. |
| Stars | `star_rating` | Never infer a rating from sentiment. |
| Original ID | `source_external_id` | Preserve; do not confuse with internal row ID. |
| Source | `source`, `source_name`, metadata | Experiment source becomes “Imported review”; do not claim a Google connection. |
| Overall sentiment | `sentiment_label` | Display saved value; Mixed remains separate from Neutral. |
| Topic/evidence | `apartment_analysis.final_result` | Present stored final result without new AI work. |
| Current access | Authenticated user's database `organization_id` | List and detail remain server-filtered. This is not yet BoomSay community access. |

Original posting dates are not established; import timestamps are not presented as review dates.
BoomSay responses, reply readiness, shared staff tasks and surveys are not connected yet.

## Approved scope and isolated setup

The user selected Lake House Apartments as the only initial test community and
supplied the BoomSay SVG assets in `services/frontend-web/public/brand/`.
Ask Genius, responses, surveys, training and multi-community switching remain later work.

Use a separate copy of the private six-review preview database. Do not point this
branch at BoomSay, Render or the original experiment database. No data importer or
provisioning process runs from this UI. No schema migration was added by this change.

Configure the frontend **before building**:

```text
NEXT_PUBLIC_BOOMSAY_REVIEW_PREVIEW=true
```

The frontend Dockerfile accepts the same name as a build argument. Retain the
isolated preview's API URL/proxy configuration; do not copy production environment files.
Configure its backend process with:

```text
BOOMSAY_REVIEW_PREVIEW=true
BOOMSAY_PREVIEW_ORGANIZATION_ID=<verified Lake House test organization ID>
APARTMENT_EXPERIMENT_ORG_ID=<the same verified test organization ID>
```

Read the actual ID from the isolated preview account/database; do not assume it is 1.
The first two settings restrict review list/detail access to that organization.
The community endpoint returns 503 for missing/invalid binding and 403 for a different
organization. The frontend waits for this authorization before mounting review screens.
The third setting uses the existing experiment startup guard to skip unrelated seed
and embedding jobs. Normal startup migrations still run, so use only the disposable
copy. Keep the experiment organization's AI disabled, provider credentials absent,
and workers/schedulers stopped. This is a read-only UI, not a new general API write policy.

Do not start the repository's general Docker Compose stack for this preview: its
shared container names, default ports and worker are not an isolated preview setup.
Rebuild only the frontend/backend in the private preview's separate installation,
retaining its dedicated database, unique ports, volumes and generated login. The
existing Mac package has not been updated by this cloud implementation.

## Verification completed

- 61 frontend tests passed (55 dashboard/regression checks plus 6 original login checks), covering presentation, inbox, private replay, preview access/navigation and existing list/detail regressions.
- Private replay renders the six saved Run 3 API records. Every saved quotation and topic count is preserved; no provider requests run.
- 18 backend endpoint checks passed using the real feedback router, JWT/auth dependencies and SQLAlchemy models in a minimal FastAPI harness, with only the database dependency redirected to disposable SQLite. Includes sorting/pagination, anonymous and invalid-token denial, cross-organization denial and mismatched token organization claims, explicit Lake House binding and disabled/misconfigured preview access.
- Changed/new component ESLint passed; whitespace checks passed.
- Full TypeScript check has **87 existing diagnostics**. Comparison against a clean worktree at the base commit found the identical set, with no added diagnostics. This is not a clean global type-check result.
- Browser checks rendered the actual Next.js app with API responses replayed from the six saved Run 3 records: inbox, negative filter, Review 5 Mixed quotation groups, rating-only stars, mobile and branded sign-in passed. This was not a live database test. The browser and temporary server were stopped.
- Google font downloads were unavailable; browser verification used fallback fonts. Production build and PostgreSQL/Redis full-stack execution have not been verified for this increment.

Run frontend checks from `services/frontend-web`:

```sh
pnpm exec vitest run __tests__/reviews __tests__/feedbacks/FeedbackDeleteRoleGate.test.tsx __tests__/feedback/FeedbackDetailActions.test.tsx __tests__/customers/FeedbackDetailCustomerLink.test.tsx
```

The private replay is skipped unless `BOOMSAY_PRIVATE_REVIEW_REPLAY` points to a
private JSON array of the six original saved API records. Keep that file outside Git.
The normal backend test file is `services/backend-api/tests/test_apartment_review_reads.py`;
the isolated verification harness used this test file unchanged.

No paid model calls, new interpretations, production changes, merges or deployments.

## Review-list refinement — 2026-10-27

Approved changes: sortable original review date; remove the inbox Analysis column;
retain the AI analysis tag in details. `review_date` is a nullable date separate
from `created_at`. Both sort directions put unavailable dates last and retain
organization filtering and pagination. The new migration adds only this field;
no import dates are copied, existing records and analysis are unchanged.
The six private saved records have no reliable posting dates and display
Unavailable. Source-date ingestion/backfill is not implemented in this change.

Validation for this refinement: 23 focused frontend tests (including the six
private saved records) and 20 backend checks passed. Backend checks used the
existing isolated SQLite harness with real API/auth/models, including date
ordering across pages and missing dates. Browser replay confirmed the new
column, missing dates, removed Analysis column and retained detail tag.
No model requests were made. These are software/display checks, not new human
assessments of analysis accuracy. Full Docker/PostgreSQL execution remains
pending on the Mac. An initial frontend invocation selected the broader suite
unintentionally: 1863 passed, 1 failed (unchanged ConfirmSuggestionDialog date
expectation), 1 skipped. That failure was not investigated or claimed fixed.
Its output is not treated as the scoped acceptance result.
Initial backend attempts failed because the old Python runtime/dependencies
were unavailable; the existing dedicated harness dependencies then ran cleanly.

Next action: apply the preview update, review the list, then define Ask Genius.
PR #2 remains a draft; no merge or production deployment is authorized here.

GitHub push of this refinement was blocked by automatic approval review;
explicit user approval to push is pending. The existing PR does not yet contain it.
