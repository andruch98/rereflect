# Ask Genius — Lake House MVP

Ask Genius answers questions about the selected community's saved reviews and
saved apartment analysis. It is the preview landing page, with personal history
and a workspace that fills the available screen. Reviews remains available.
Surveys, management responses, tasks, and portfolio comparisons are not connected.

The approved product behavior is in APPROVED_MVP.md. The executable instructions
are in services/backend-api/src/services/ask_genius_instructions.txt; the service
adds a small runtime data/output contract.

## Conversation, periods, and questions

A manager chooses a period before starting unless they explicitly saved a
default. Choices include rolling 7/14/30 days, last calendar month/quarter,
last six months, year to date, custom dates, and all available history.
Calendar boundaries use America/New_York. The resolved dates are sent with the
evidence; review import timestamps are never substituted for posting dates.

The period is stored with each conversation and restored with its history.
A temporary period override does not change the account preference. The picker
and supported explicit chat commands can save or clear only the signed-in
manager's default. A nullable users.ask_genius_default_period field is added by
migration d0c6241e9f32. Existing users have no automatic default.

Four approved starters cover topics, complaints, praise, and star-rating counts.
Selecting a starter fills the editable composer; sending starts the request.
Browse more questions separates Reviews and Analysis. Future source categories
remain hidden until the server reports that they are connected.

## Evidence and answers

The fixed authenticated read/calculate/answer flow does not reanalyze reviews.
SQL selects the authorized community and original review dates before evidence
is sent to the model. Finite periods exclude undated records and disclose missing
date coverage. All available history includes them only by explicit selection.
No-data answers are produced locally without a model request; they distinguish
dated absence from an inability to place undated reviews.

Original statements are separate from saved interpretations and code-calculated
counts. Mixed quotation sentiment is preserved. A rating-only review supplies no
written explanation. Reviews are not unique residents or proof of complete
community history. Unsupported calculations and comparisons require clarification.

Answers lead with the finding, use short paragraphs/bullets, and avoid repetition.
Normal answers and explanations are capped at 1,000 characters including spaces.
Only requested evidence may expand the complete answer to 3,000 characters; the
explanation itself remains within 1,000. A headline count or citation alone does
not qualify. Oversized output is rejected without truncating meaning or retrying
the provider automatically.

The model returns a short explanation and structured references. Server code
validates review IDs against the selected cohort, checks exact excerpts and saved
topics, and renders links to the original reviews. The client permits only those
authorized internal links. It does not render model-supplied external links,
images, or raw HTML. Relevant contrasting evidence should be retained.

## Access and configuration

Source records cannot be changed through this path. Writes are limited to the
manager's conversation, internal request/usage history, and explicit personal
default-period updates. No response publisher, task executor, arbitrary SQL
generator, web search, analysis worker, embeddings, or new agent framework was
added. Authorization is enforced in code rather than delegated to the model.

The feature requires ASK_GENIUS_ENABLED=true plus explicit provider/model
configuration. Existing adapters support openai, openai_compatible, and ollama.
OpenAI uses a separate ASK_GENIUS_API_KEY and its official endpoint. Compatible
or local providers require ASK_GENIUS_BASE_URL. The update preserves the
previously selected model and connection; it does not change provider settings.

Evidence is bounded at 100 selected reviews and 80,000 evidence characters,
without silent sampling. At most 10 prior messages are included. Generation
has a 45-second timeout, 1,200 completion tokens, and no automatic retry.
This is a bounded MVP rather than an arbitrary analytics engine.

History reuses Conversation/Message tables with a dedicated scope and creator/
organization checks. Legacy chat paths exclude that scope. Request IDs prevent
duplicate generation after uncertain failures. PostgreSQL uses a session advisory
lock; isolated SQLite tests exercise the process lock.

## Mac update

The source-only updater in preview_updates preserves the existing connection,
credentials, login, database, and blocked review-analysis configuration. The
recognized preview startup already runs Alembic before the API, so it applies the
new nullable preference field on restart. Packaging pins an exact source commit.

Updater file-copy failures can restore the prior source before startup. Once the
new database migration has run, restoring old source alone is not a supported
rollback because that source cannot resolve the new Alembic revision. Keep the
backup and use the recovery guidance in the package. No production deployment
or merge is part of this change.

## Verification of this increment

- 83 focused frontend tests passed. ESLint has no errors and three existing
  warnings. Full TypeScript output matches the baseline: 87 existing diagnostics,
  with none added.
- 29 isolated backend integration/migration tests and 71 period/parser tests
  passed. A further 14 existing Ask Genius regressions passed through the lean
  harness; one private-fixture test was skipped and two full-app legacy/WebSocket
  route tests were excluded because the harness does not load those routers.
- The migration test preserves an existing user, adds a nullable preference with
  no default, and verifies downgrade. Alembic has one head.
- 16 real localhost HTTP checks passed using real JWT/auth/routes/SQLite and a
  simulated provider. They cover period enforcement, replay, evidence links,
  persistence, temporary overrides, missing dates, clarification, and isolation.
- 14 source-updater and four archive-builder tests passed. These use disposable
  files and synthetic configuration. They do not establish actual Mac/Docker
  behavior.

Actual provider calls: zero. Tests do not establish the factual quality of live
model answers. PostgreSQL advisory locks, actual Mac/Docker startup, and live
provider behavior remain unverified in this environment. Current visual browser
validation was blocked: the connected browser was unavailable and the cloud
browser could not reach the local test server. UI tests passed, but they are not
a substitute for checking the updated Mac preview.

The earlier layout increment had browser checks; those do not validate these new
controls. The next human check is to apply the update, review the period controls
and evidence links, and assess real answers against the saved community records.
