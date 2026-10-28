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
Selecting a starter fills the editable composer even before a period is selected;
only sending requires a period and starts a request. Browse more questions uses
Review, Analysis, Survey and Management response tabs. Disconnected categories
remain visible and labeled, with their questions unavailable. The period picker
is prominent, default saving is secondary and missing-date coverage is condensed.
Its required-period state persists independently of focus, including while editing
the composer or an incomplete custom range, and clears when a valid period is chosen.

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

Answers lead with relevant complaints and concerns unless positives only are
requested. Positive findings otherwise appear only when needed to answer the
question accurately. Distinct findings use bullets, explanations use short
paragraphs with blank lines, and ranked priorities use numbers with reasons.
Verified frequency, reported seriousness and reliable recency inform priorities;
old complaints are not assumed current or unresolved. Follow-ups retain the same
topics and distinguish star ratings from saved sentiment. Avoid repetitive
conclusions, unnecessary names and broader-topic counts on narrower claims.
Normal answers and explanations are capped at 1,000 characters including spaces.
Only requested written source detail may expand the complete answer to 3,000 characters; the
explanation itself remains within 1,000. A headline count or citation alone does
not qualify. Oversized output is rejected without truncating meaning or retrying
the provider automatically.

The policy is organized by scope, verification, presentation and writing, with
seven distinct examples. The runtime contract defines selectors rather than
restating product rules. The context explicitly separates the maximum expanded
message size from the explanation limit and requires actual written source detail.
Validated verbatim review excerpts may use the additional room; overlapping
excerpts count once. Popup-only references do not qualify. The existing explicit
saved-analysis allowance remains, with semantic substance and explanatory-prose
discipline enforced by instructions, not proven by the presence of a reference.

The exact short negative-topic-to-review follow-up can attach sources locally
without another model call. It accepts only an initial broad negative-topic
exchange or the approved frequency → negative topics → reviews sequence, with
an exact flat topic list, no numeric claims, and a matching negative source for
every topic. It checks that authorized review data and resolved dates are unchanged
from the prior model request. Other wording, longer conversations, narrower themes,
changed filters/data and ambiguous scopes follow the ordinary model path with the
consolidated context instructions. This is deliberately not a general intent engine;
it validates topic/source membership, not every descriptive claim in prior prose.
Only the latest ten messages are supplied to the model; no indefinite-memory claim
is made. Exact topic labels with a parenthetical qualifier also retain inline popup
placement in the renderer.

The model returns a concise explanation and validated evidence selectors. For a
complete review list it can supply allowlisted rating/topic/sentiment filters;
server code selects every match in the authorized period cohort in stable order.
Specific themes still require individually verified source IDs rather than a
broader filter. Records are deduplicated per topic, not across different topics.

Topic bullets use exact saved topic labels and receive View review / View N reviews
controls immediately underneath. Direct review lists use a single collection link.
No long source cards or internal review numbers lead the chat. Full original
reviews and expandable saved analysis appear only inside the popup. The popup
shows at most 50 records. Selecting Show remaining N / Show next 50 reviews adds
an additional displayed evidence message for the next subset, without a provider
request. These presentation pages reset when the answer is remounted; the complete
selected evidence stays in stored message metadata and public snapshots.

Only LLM-written text counts toward the 1,000/3,000 limits; application controls,
original reviews and saved analysis in popups are exempt. Optional model-copied
excerpts remain exact-match validated. The renderer disables model URLs, images
and raw HTML. Legacy private reviews load through authenticated APIs only when
a popup opens. Public snapshots never request private review endpoints.

The share-copy confirmation is a high-contrast green banner at the viewport's
top center with a checkmark and dismiss button, and no Manage links option.

## Access and configuration

Source records cannot be changed through this path. Writes are limited to the
manager's conversation, internal request/usage history, explicit personal
default-period updates, and explicitly published chat snapshots. No response publisher, task executor, arbitrary SQL
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

## Chat management and public snapshots

The sidebar remains visible with New chat / Your chats wording, personal custom
names, pinning and a three-dot Rename / Pin or Unpin / Share / Delete menu.
Deletion removes a private chat from its history; published snapshots persist.
The confirmation states that distinction. e1d7352fa043 adds a false-by-default
conversations.is_pinned field and the ask_genius_shares table.

Share creates a new frozen snapshot and copies an unguessable public bearer link.
Only the SHA-256 hash of its random 256-bit token is stored. Anonymous reads return
an allowlisted snapshot DTO, not live chat/database queries. Selected sources are
revalidated for organization ownership at publication and copied into the snapshot;
source and message identifiers are local to the snapshot. Raw requests, provider
responses, private preferences and unrelated reviews are omitted. No sign-in,
editing, link-management or revocation feature is added to the shared view.

Public responses use no-store/noindex/no-referrer. Preview Mixpanel and Sentry
recording/tracing are disabled so bearer links and resident content are not sent
to configured telemetry exporters. Existing non-preview behavior is preserved.
The public renderer cannot resolve sources via the private review API.

Failed requests return a saved chat reference, period and safe error category.
The question remains visible with a local Retry control. Known failed requests
use a new ID for an explicit retry; uncertain transport errors reuse the same ID
to prevent a second model call if the first actually completed. Server audit data
records format/incomplete-output distinctions without exposing raw errors to users.

## Mac update

The source-only updater in preview_updates preserves the existing connection,
credentials, login, database, and blocked review-analysis configuration. The
recognized preview startup already runs Alembic before the API, so it applies the
additive migrations for preferences, pins and snapshot storage on restart. Packaging pins an exact source commit.

Updater file-copy failures can restore the prior source before startup. Once the
new database migration has run, restoring old source alone is not a supported
rollback because that source cannot resolve the new Alembic revision. Keep the
backup and use the recovery guidance in the package. No production deployment
or merge is part of this change.

## Verification of the 28 October increment

- 171 backend checks passed: 75 isolated flow/service/chat/snapshot/migration
  checks, 71 period/parser checks, 21 mutation-RBAC checks and four preview
  telemetry checks. The migration test preserves existing chats, verifies
  upgrade/downgrade and checks that Alembic has one head.
- 112 frontend tests passed, one private saved-run fixture was skipped. This
  includes reviews, message cards, modal analysis, anonymous public auth,
  history controls, retry states, analytics guards and existing auth/API-client
  regressions. Focused ESLint is clean. Full TypeScript reports the same 87
  baseline diagnostics, with no additional errors.
- 22 real localhost HTTP checks passed with actual JWT/auth/routes/SQLite and a
  simulated provider. They cover contextual source requests, popup payloads,
  per-user mutation authorization, anonymous snapshots, frozen history and
  deletion behavior. Three simulated model calls; zero actual provider calls.
- 17 updater and five builder checks passed using disposable files and synthetic
  private data. Final delivery also replays the exact committed ZIP against the
  previously delivered source archive with both recognized startup variants.

The prior implementation rejected full-review transcription and rigid formatting
failures wholesale. Structured selection avoids those reproduction cases, and
safe errors now preserve a recoverable chat. The actual causes of the user's Mac
failures cannot be confirmed without its audit records; this implementation does
not claim that those unseen records were inspected.

No live model calls or charges were made. Model answer quality, real provider
connectivity, actual Mac/Docker startup and PostgreSQL advisory-lock operation
remain preview checks. A headless browser was unavailable and its download failed
in this environment, so component tests do not establish final visual fidelity.
The approved PDF is the visual reference; review the running Mac preview against
it. The loopback-only preview supports signed-out sharing on that same Mac;
remote recipients require a publicly reachable deployment. No network configuration,
production deployment or merge is included.

## Review-links revision verification

180 backend checks and 99 frontend tests passed (one private fixture skipped),
plus 22 updater tests. New checks cover 78 matching reviews, 50/28 popup pages,
topic-to-review placement, duplicate references, strict filters, popup length
exemption, and the dismissible share banner. ESLint passes on edited UI files.
The prior TypeScript diagnostics remain; no new Ask Genius diagnostic appears.
No live model charges or Mac/Docker/browser visual verification are claimed.
The existing 100-review / 80,000-character model-context guard remains in place;
popup pagination does not silently widen that cohort or bypass its cost bound.

## Context and instruction revision verification

252 backend checks passed, including the reported three-turn conversation,
explicit broadening, changed periods/data, topic-level negative evidence inside
positive overall reviews, and written-source length allowances. 106 frontend tests
passed with one private fixture skipped, including persistent period highlighting
and exact topic/parenthetical popup placement. All 22 updater/build checks passed.
Focused ESLint is clean; the TypeScript diagnostic set is unchanged at 87.
The consolidated policy has seven distinct examples and 1,855 words versus 2,041
in its predecessor. These checks use simulated responses, not live provider calls;
they establish the application behavior and prompt delivery, not guaranteed LLM
compliance or Mac/browser visual fidelity.
