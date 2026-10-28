# Isolated apartment review experiment

This opt-in mode uses Rereflect's CSV API → PostgreSQL → Redis/Celery analysis
worker → existing OpenAI provider → PostgreSQL → feedback list/detail API.
The apartment result is `apartment_analysis`; `star_rating` is a new nullable
integer column. The existing String sentiment column already accepts mixed and
unknown, so no enum coercion or enum migration is needed.

Only run in a fresh experimental database and organization, with no integrations,
automations, outbound mail credentials, webhooks or production connections.
Keep all real inputs, source IDs, ledgers and exports outside the checkout.
Upstream LICENSE and NOTICE remain unchanged.

See [Runtime rejection and fallback checks](RUNTIME_CHECKS.md) for the exact
acceptance conditions, whole-result versus field-level effects, and distinctions
between runtime gates, offline tests and informational warnings.

## Setup and input

Use the repository's PostgreSQL/Redis setup and dependencies. Apply
`alembic upgrade head` from `services/backend-api`. Configure an isolated
organization with AI analysis enabled and the selected OpenAI categorization model.
Set these variables on both API and worker processes:

- `DATABASE_URL`, `REDIS_HOST`, `REDIS_PORT`: isolated experiment services.
- `APARTMENT_EXPERIMENT_ORG_ID`: the isolated organization ID.
- `APARTMENT_EXPERIMENT_MODEL`: the one selected, compatible OpenAI model.
- `APARTMENT_EXPERIMENT_MANIFEST`: absolute path to private `manifest.json`.
- `APARTMENT_EXPERIMENT_LEDGER`: absolute path to a private persistent SQLite file.
- `APARTMENT_ANALYSIS_TEST_RUNS_PATH`: absolute path to the private, shortened
  `review_analysis_test_runs_v1.txt` on the worker's filesystem (see below).
- `OPENAI_API_KEY`: securely injected credential; never pass it on the command line.
- `JWT_SECRET` and `LLM_ENCRYPTION_KEY`: fresh isolated application secrets, as
  required by the ordinary app and migrations.

The experiment bypasses the normal retrying organization LLM resolver, but uses
Rereflect's existing provider factory and OpenAI provider. This allows the injected
environment key without copying another app's environment or storing that key in
Git. There are no secondary providers, models or SDK retries. Non-OpenAI provider
configurations fail explicitly. The prompt uses temperature 0.1, OpenAI strict
Structured Outputs (`json_schema`) and a 4,096-token output allowance. Use a model
supporting that response format; the previous runs used `gpt-4.1-mini`. The schema
allows only the 21 topic names and the agreed sentiment/quotation fields. Ordinary
Rereflect requests retain their existing JSON-mode behavior. Non-`stop` completions fail validation without
truncating or repairing raw output.

### Private analysis reference

Supply the shortened AI-facing file, not the full technical archive or unapproved
draft corrections. Keep it outside Git, on a private persistent volume readable by
the worker. In a container, use its mounted path. This repository intentionally
does not contain real reviews or the private file; no public download or embedded
copy is used. The filename is also ignored by Git as an extra safeguard.

Before every apartment AI request, the client reads the complete UTF-8 file from
`APARTMENT_ANALYSIS_TEST_RUNS_PATH`. It neither caches nor truncates it. A missing,
relative, unreadable, invalid-UTF-8 or empty file produces an explicit failed audit
and the existing keyword fallback **before** reserving or sending a model request;
the file is never silently omitted. The AI-disabled comparison needs no reference.

The request contains, in order:

1. Current analysis instructions, including an introduction telling the model to
   read the history, compare original reviews with analyses and reviewed comments,
   and apply the approved lessons. Historical outputs can contain mistakes; a
   passing code check does not approve their interpretation. Current instructions
   and output format take precedence over historical material.
2. A separate user message containing the full file under
   `analysis_test_runs_reference`. It is reference material, not the current review.
3. The unchanged current review text and star rating. This remains last so the
   existing manifest integrity check still verifies exactly the intended input.

The model must use the current review's evidence rather than copy historical
names, facts, quotations or topics. A non-null `approved_corrected_analysis` is an
approved complete example; null is not. `ai_attempt.reference_file` records the
file's SHA-256 and byte count, while the existing private request audit/ledger
retains its exact content. These records must stay private too. The file adds input
tokens to every call; its effect on interpretation needs a separately authorized
live test. Reusing reviews already in the reference tests known cases, not unseen
review performance.

First inspect the real CSV headers. Write the six authorized IDs, in order, to a
private JSON array. Do not infer column names from previous workspaces. Then run:

```sh
python experiments/apartment_reviews/prepare_input.py \
  --csv /private/source.csv --ids /private/ids.json \
  --id-column ACTUAL_ID_HEADER --text-column ACTUAL_TEXT_HEADER \
  --rating-column ACTUAL_RATING_HEADER --output /private/selected
```

The destination must not exist. Selection requires exactly one occurrence of each
ID and usable ratings. Original text, including whitespace and newlines, is
preserved. The current review contributes only text/rating to the model; the
private reference is supplied separately. IDs remain internal metadata. The
source is untouched. Generated files contain only the normalized fields needed
for the experiment, with separate AI and fallback CSVs.

## Run once

Start the ordinary API and worker (no Beat). The API still runs migrations, but
experiment mode skips startup seed jobs (including Copilot embeddings and BYOK
key seeding); provision the isolated organization/user explicitly. In experiment mode the worker loads
only the analysis task module, disables its schedule/retries/side effects, and
runs with concurrency/prefetch 1. Do not start another worker against this broker.
Use an authenticated session belonging to the isolated organization. Import
`ai.csv` once through `POST /api/v1/feedback/import-csv`. Import queues one batch
containing the six exact newly created IDs, processed in input order; do not also
manually trigger analysis. Wait for the six saved outcomes. Then import
`fallback.csv` once through the same endpoint. The separate source selects the
AI-disabled comparison path and cannot overwrite the AI records.

The provider atomically reserves each approved source ID in the persistent
ledger before calling the SDK. This limits the run to six attempted requests,
including failures. Re-delivery cannot make a second paid attempt. A crash after
reservation is conservatively counted; investigate the ledger before any rerun.
Authentication/permission/bad-request/unavailable-model errors stop subsequent
provider attempts. A stopped or duplicate attempt is reported explicitly. Never
change/delete the ledger to get another attempt without separate authorization.

The worker first cleans predictable formatting, then validates required fields,
allowed labels/names, unique topics and nonempty source quotations. Label case and
surrounding spaces, explicit `and`/`&` topic aliases, `quotes`/`quotations`, single
topic/quotation list formatting, explicit null topics, extra fields, identical
duplicates and blank quotation entries are handled without another model call.
Whitespace, straight/curly quotation marks and a quotation's opening English
letter case may differ (`She` versus `she`). Case changes later in a quotation
still fail. The accepted quotation is the original contiguous source text.
Every correction is recorded in `ai_attempt.normalizations`. Raw output and source
input remain unchanged; `parsed_result` is the cleaned, validated result.
Conflicting duplicate topics, missing required information, unsupported words,
typo repair, joined passages and JSON extraction remain failures. There is no
partial acceptance: a remaining failure still triggers whole-result fallback.
Validation cannot assess interpretation. See the runtime guide for precise rules.
A rating-only review has no topics/quotations; 1–2 stars → negative, 3 → neutral,
4–5 → positive. Text-bearing fallback uses the existing VADER SentimentAnalyzer.
Fallback topic sentiments are unknown; exact keyword spans are mechanical
evidence, not AI-selected quotations. No fallback model calls occur.

## Labeled quotation format

New AI calls return each quotation as `{"text": "exact source passage", "sentiment": "positive"}`
inside the topic's `quotations` list. Quotation labels are positive, negative,
neutral or unknown. Each topic appears once, including when different employees
or time periods receive different judgments. Genuine praise and complaints belong
in a single mixed topic, with at least one positive and one negative quotation.
The AI performs that interpretation; code does not merge conflicting topics.

The live client requires labeled quotations. When one topic has both positive and
negative quotation labels, code sets that topic to `mixed` and records the change
in `normalizations`, instead of rejecting the analysis. A topic already labeled
mixed still needs both sides. Other labels are left as supplied; code does not
invent missing evidence or merge conflicting duplicate topics. The same exact
quotation cannot have conflicting labels within one topic. These checks cannot
prove that the AI assigned the correct sentiment. Source matching and harmless
format cleanup still apply to each quotation's text and label. A single quotation
object is wrapped in a list; extra object fields are ignored with an audit entry.
Missing labels are not inferred from the topic. Historical output can still be
replayed with the validator's default legacy mode, without rewriting or labeling
it; this mode is not used for new live calls. Keyword evidence remains unchanged.

Overall sentiment remains the model's interpretation of the review's main message
and emphasis. It is not a vote across topic labels, and a mixed topic does not
automatically make the entire review mixed. Code never changes overall sentiment
as a side effect of deriving a mixed topic.

The Markdown export groups labeled quotations under Positive, Negative, Neutral
or Unknown beneath each topic. Historical strings and mechanical fallback spans
are explicitly Unlabeled. The JSON export retains the full audit. This change
covers the experiment report, not the upstream browser dashboard.

### Further live testing

The two earlier six-review runs are complete; their allowances are consumed.
These schema/reference/normalization changes have only been tested offline.
A new paid run needs its own explicit allowance, a new isolated experiment
organization and private ledger/output directory. Preserve earlier results and
ledgers; never clear them or overwrite completed analyses to obtain another call.

Before a separately authorized run, verify the actual cloud task has the securely
configured key, original private manifest/CSV, and the latest shortened reference
file at `APARTMENT_ANALYSIS_TEST_RUNS_PATH`. This development workspace has no
injected API key or original private CSV. Do not silently reconstruct authoritative
input from a report. Follow the import/worker/export procedure above, including
the no-cost keyword comparison. Keep private inputs, credentials and identifiable
results out of Git, and leave new interpretation approvals blank until reviewed.

## Export and review

After both runs, read back with the existing feedback API. To export:

```sh
# REREFLECT_TOKEN is a securely supplied JWT for the isolated organization.
python experiments/apartment_reviews/export_results.py \
  --api-url http://127.0.0.1:8000 --organization-id EXPERIMENT_ORG_ID \
  --manifest /private/selected/manifest.json \
  --ledger /private/attempts.sqlite --output /private/results
```

The new output directory contains readable Markdown and complete JSON, including
full inputs, provider requests/responses, raw/parsed/saved AI comparison, separate
fallback records, checks, timestamps, source hash, commit, token usage and blank
approval/comments/corrections. Monetary cost is unavailable unless separately
substantiated. Move these files to the environment's persistent output mechanism;
a temporary directory alone is not a handoff.

The existing UI can show review text and legacy sentiment fields. It has not been
redesigned or tested for the new topic/evidence payload, rating or audit fields;
use the export/API for complete review. Legacy charts/filters may only recognize
the original three sentiments. No claim is made about their mixed/unknown display.

Urgency/risk/suggested-action, Copilot, reports, responses and other modules retain
their ordinary behavior outside this mode. Apartment analysis leaves ancillary
problem/urgency/risk/action fields unset/default, skips learned classifier
supersession and downstream assignment/automation/webhook jobs, and never forces
praise into a software problem category. No new follow-up feature is implemented.

## Offline verification

```sh
PYTHONPATH=services/worker-service:services/analysis-engine/src \
  python -m pytest experiments/apartment_reviews -q
```

For a full transport check, migrate a disposable PostgreSQL database, start an
isolated Redis, and export its configuration plus temporary JWT/encryption
secrets. Then run:

```sh
APARTMENT_TEST_WORKDIR=/private/test-artifacts \
PYTHONPATH=services/backend-api \
  python experiments/apartment_reviews/check_pipeline.py
```

This imports twelve fictional records via the real router, consumes actual Redis
jobs with a real Celery process, and verifies PostgreSQL/API/export round trips.
Only the external OpenAI SDK transport is replaced; it never makes paid calls.
Auth dependencies are overridden. Login, full server startup, frontend and live
provider semantics are not covered. The child worker always terminates afterward.
The tests never use real review IDs/text or send test examples to a live model.
