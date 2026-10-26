# Apartment experiment: runtime rejection and fallback checks

This describes the implementation originally published at
`6ea798cce29fef15c86f533679b90b380733cc97`, including the subsequent straightforward
formatting cleanup on this branch. Examples below are fictional.
The scope is the opt-in apartment CSV → worker → OpenAI → persistence path, including
its input and call-budget gates. Ordinary software-feedback analysis is a different
path: `_analyze_feedback_item` returns immediately after the apartment path when
`APARTMENT_EXPERIMENT_ORG_ID` was truthy at worker import time.

## Outcomes and source key

- **Fallback**: reject the **entire AI result**, not just the offending topic or
  field. `categorize_apartment_feedback` records a failed audit with
  `parsed_result=None`; `_analyze_apartment_item` computes a complete keyword result.
  Raw output is retained when the provider returned it to the categorization
  function. `final_result.method` becomes `keyword_fallback`, `llm_analyzed=False`,
  and `llm_analysis_pending=False`. There is no paid retry or partial salvage.
- **Block**: fail before an analysis is accepted; **no automatic fallback** at that
  boundary. The batch counts an item failure; the single-item task raises. In
  experiment mode these tasks have no configured paid retry.
- **Skip**: leave a previously completed result intact or omit an ineligible item.
- **Import rejection**: reject the upload/row before worker analysis; no AI or
  keyword fallback is run for that rejected input.

Source abbreviations in the tables refer to these exact files; function names are
given in each row:

- **Contract**: [worker `src/apartment_reviews.py`](../../services/worker-service/src/apartment_reviews.py)
- **Client**: [worker `src/llm_client.py`](../../services/worker-service/src/llm_client.py)
- **Worker**: [worker `src/tasks/analysis.py`](../../services/worker-service/src/tasks/analysis.py)
- **Provider**: [worker `src/llm/providers/openai.py`](../../services/worker-service/src/llm/providers/openai.py)
- **Factory**: [worker `src/llm/factory.py`](../../services/worker-service/src/llm/factory.py)
- **Ledger**: [worker `src/llm/experiment.py`](../../services/worker-service/src/llm/experiment.py)
- **CSV**: [API `src/services/apartment_import.py`](../../services/backend-api/src/services/apartment_import.py)
- **API**: [API `src/api/routes/feedback.py`](../../services/backend-api/src/api/routes/feedback.py)
- **Sentiment**: [analysis engine `src/analyzer/sentiment.py`](../../services/analysis-engine/src/analyzer/sentiment.py)

## Formatting cleanup before AI response acceptance

`validate_result` returns a canonical analysis and optionally records corrections
in the caller's `normalizations` list. The client saves that list as
`ai_attempt.normalizations`, even if a later check fails. Raw output, the provider
response and original review text are never rewritten. Existing saved analyses
and request ledgers are not automatically revisited or updated.

Permitted corrections, performed without model calls:

- Trim and lowercase sentiment labels; normalize whitespace/case in topic names.
- Map only the 21 canonical names and their explicit `&` → `and` alternatives
  back to canonical topic names. No fuzzy matching or new semantic synonyms.
- Accept `quotes` as an alias for `quotations`. If both are present, their JSON
  values must be identical; otherwise fail instead of choosing one.
- Ignore extra top-level/topic fields in the canonical result, while retaining
  them in raw output. Required fields must still be present.
- Convert explicit `topics: null` to `[]`, a single topic object to a one-item
  list, and a quotation string to a one-item list. Missing topics are not empty
  topics; other malformed types still fail.
- Remove identical duplicate JSON keys. Equality compares serialized decoded
  values, preserving distinctions such as `false` versus `0`, even when nested.
  Conflicting duplicate keys still fail, including within extra fields.
- Remove blank string quotations when usable evidence remains and deduplicate
  repeated source quotations. Non-string or unsupported nonblank quotations still
  fail; an empty final quotation list still fails.
- Remove identical topic entries after cleanup. Entries with the same topic but
  different sentiment or different evidence (including evidence order) still fail.
- Match quotations exactly first. Otherwise permit only whitespace runs and
  straight/curly single/double quotation-mark differences. Return the matching
  contiguous **original** source passage, never rewritten evidence. Quotation
  capitalization, other punctuation, words, numbers, typos and joined passages
  are not repaired. If several passages match, the first matching source passage
  is used; this does not establish contextual relevance.

JSON extraction from prose/code fences, conflicting-topic merging, semantic
repair, technical-error reclassification and partial results remain deferred.
An explicit null topic list is formatting-compatible, not proof of completeness.

## AI response acceptance: all remaining failures reject the whole analysis

Every row below has the **Fallback** outcome defined above. None removes or fixes
only one field. The first encountered error is recorded; validation does not
collect every possible error in an invalid response.

| Exact failing condition | Meaning | Harmless-looking example, where applicable | Source / function |
| --- | --- | --- | --- |
| `response.finish_reason != "stop"` (including `None`) | Provider did not declare a normal completed response. This check precedes JSON validation. | Syntactically complete JSON with finish reason `length` is still rejected. | Client / `categorize_apartment_feedback` |
| `json.loads(raw, object_pairs_hook=pairs)` raises | Output is not parseable as the required JSON document. No fence stripping, extraction or repair is attempted. | Markdown fences or an introductory sentence around otherwise valid JSON. | Contract / `validate_result` |
| An object key occurs twice with different decoded JSON values | Conflicting values remain ambiguous; identical duplicates are removed. The hook applies to every parsed object. | `positive` versus `positive ` in duplicate keys still conflicts before label cleanup. | Contract / `validate_result.pairs`, `_same_json` |
| Parsed result is not a `dict`, or lacks `sentiment` or `topics` | Required outer information is missing. Extra fields are ignored. | An array wrapping one valid object still fails. | Contract / `validate_result` |
| Overall sentiment is not a string or its trimmed, case-folded value is not in `SENTIMENTS` | Only positive, negative, mixed, neutral, unknown are accepted after label cleanup. | `mostly positive` remains unsupported; `Positive ` passes. | Contract / `validate_result.sentiment` |
| `topics` is neither a list, a dictionary nor null | Topics must be a list after single-object/null conversion. | A string containing JSON is not reparsed. | Contract / `validate_result` |
| Any topic is not a dictionary, lacks name/sentiment/evidence, or has conflicting `quotes` and `quotations` | Required topic fields must be recoverable without guessing. Extra fields are ignored; only `quotes` is an accepted field alias. | `quote` (singular) is not an approved alias. | Contract / `validate_result` |
| Topic name is not a string or is absent from `TOPIC_NAMES` after whitespace/case normalization | Names must match the canonical list or explicit and/ampersand aliases. | `Maintenance` still fails; `Maintenance and repairs` passes. | Contract / `validate_result`, `_topic_key` |
| A normalized topic name already belongs to `seen` with a different canonical topic object | Only identical duplicates are removed; no conflicting-topic merge. | Separate positive/negative entries or different evidence still fail. | Contract / `validate_result` |
| Topic sentiment is not a string or its trimmed, case-folded value is not in `SENTIMENTS` | Per-topic sentiment uses the same allowed vocabulary. | `Mostly negative` remains unsupported; `Mixed ` passes. | Contract / `validate_result.sentiment` |
| Quotations are neither a list nor a string, or no nonempty quotations remain after cleanup | Every included topic needs usable evidence. | Null or a list of only blanks still fails; a single valid string passes. | Contract / `validate_result` |
| Any quotation is not a string | Malformed evidence is not silently discarded. Blank strings may be removed, non-strings may not. | A null entry alongside a valid quotation still fails. | Contract / `validate_result` |
| A nonblank quotation cannot match a contiguous source span after the permitted whitespace/quote-mark comparison | Actual wording and other punctuation must still match. Accepted evidence is restored to the source's exact wording. | Correcting a typo, changing capitalization or joining passages with an ellipsis still fails. | Contract / `validate_result`, `_source_quotation` |
| `not text.strip()` and either topics are nonempty or sentiment differs from `rating_sentiment(rating)` | Empty/whitespace-only reviews must have `topics=[]`; ratings 1–2 → negative, 3 → neutral, 4–5 → positive. | `unknown` for an empty four-star review is rejected despite being an allowed label generally. | Contract / `validate_result`, `rating_sentiment` |

JSON key ordering and formatting whitespace **outside string values** do not
cause rejection. Different JSON escapes that decode to the same string are fine.
Repeated quotations within one topic are deduplicated, not rejected. A text-bearing review may
have an empty topic list. Validation does **not** prove topic completeness, correct
sentiment, relevance of a quotation, or that a `mixed` topic's evidence really
contains both praise and complaints. Those remain human-review questions.

## Worker input, eligibility and configuration gates

| Exact failing condition / branch | Plain-English meaning | Outcome and scope | Harmless-looking example | Source / function |
| --- | --- | --- | --- | --- |
| Single-item lookup returns no feedback | Requested record does not exist. | Skip whole item; return `not_found`. | None. | Worker / `analyze_single_feedback` |
| Single-item `sentiment_label is not None`; batch query excludes IDs outside the organization, IDs not requested, and rows whose sentiment is non-null | Analyze only eligible, unanalyzed records. | Skip whole item; single returns `already_analyzed`; empty batch returns `no_items`. | Re-delivery of the same completed job. | Worker / `analyze_single_feedback`, `analyze_feedback_batch` |
| `str(feedback.organization_id) != APARTMENT_EXPERIMENT_ORG_ID` | Protect the isolated organization. | Block whole item. | Environment value `"01"` does not equal database ID `1` rendered as `"1"`. | Worker / `_analyze_apartment_item` |
| Source is neither `apartment_review_ai` nor `apartment_review_fallback` | Prevent unrelated records from entering this experiment. | Block whole item. | Different capitalization or trailing space in the source name. | Worker / `_analyze_apartment_item` |
| `feedback.apartment_analysis is not None` | Do not overwrite an existing experiment outcome. | Skip whole item, including an existing fallback. | Re-running after a previous fallback does not replace it. | Worker / `_analyze_apartment_item` |
| Text is not `str`; rating is `bool`, is not `int`, or is outside 1–5 | Original text and usable numeric rating are mandatory. Empty text is valid. | Block whole item before provider invocation. `messages` also calls this validator before the client's catch block; fallback calls it too. | Rating `4.0` or `"4"` must be normalized before reaching the worker; `True` is rejected despite Python treating it as an integer. | Contract / `validate_input`, `messages`, `keyword_result`; Worker / `_analyze_apartment_item` |
| `not feedback.source_external_id` | Exact source mapping is required. | Block whole item. | None. | Worker / `_analyze_apartment_item` |
| Organization query returns no organization | The configured organization is missing. | Block whole item. | None. | Worker / `_analyze_apartment_item` |
| AI-source record and `not org.ai_analysis_enabled` | An intended AI run must actually have AI enabled. | Block whole item, not silent fallback. | A disabled toggle is a configuration failure. | Worker / `_analyze_apartment_item` |
| AI config exists and `config.default_provider != "openai"` | Only the chosen OpenAI path is supported. | Block whole item before the client; does not set the ledger's shared-stop flag. | `"OpenAI"` differs from `"openai"`. | Worker / `_analyze_apartment_item` |
| Source is `apartment_review_fallback` | Explicit comparison run, not an AI failure. | Whole result uses keyword fallback with `ai_attempt=None`; no provider call. | Not applicable: intentional selection. | Worker / `_analyze_apartment_item` |
| Client returns an audit with `parsed_result is None` | AI did not produce an accepted result. | Fallback for the whole analysis; preserve failure reason. | Includes every response-validation failure above. | Worker / `_analyze_apartment_item` |

The selected model is environment override → organization categorization model →
`gpt-4o-mini`. There is no additional local model-availability check or star-rating
versus text-sentiment consistency check. An unsupported model is handled by the
provider-error path below. Missing experiment configuration does not activate
these protections: API and worker must both start with experiment mode configured.

## Provider and durable request-budget gates

Failures below occur inside the client's `try` unless stated otherwise. They yield
**whole-analysis Fallback**, even if no HTTP request was made. `provider_attempted`
only becomes true after a durable reservation; a crash after reservation is
conservatively counted. Do not equate a fallback record with a paid attempt.

| Exact failing condition | Plain-English meaning / consequence | Harmless-looking example | Source / function |
| --- | --- | --- | --- |
| `not os.environ.get("OPENAI_API_KEY")` | Missing/empty key: no provider request; failed audit and fallback. Does not globally stop other records. | None. | Client / `categorize_apartment_feedback` |
| Experiment active and provider name is not `"openai"` | Factory blocks secondary providers. In the apartment client, this would be caught and cause fallback; other callers receive the exception. | Provider capitalization differs. | Factory / `LLMProviderFactory.create` |
| Experiment active and `not request.experiment_key` | Block unrelated paid OpenAI calls before SDK invocation. Other callers receive `ExperimentBlocked`; the apartment client would record fallback. | Missing internal source metadata. | Provider / `OpenAIProvider.complete` |
| Missing manifest environment value | Cannot verify the authorized six records; block before reservation/HTTP. | None. | Ledger / `reserve` |
| Manifest records length is not 6, or distinct source-ID count is not 6 | Approved input set must contain exactly six unique records. | An accidental duplicate row. | Ledger / `reserve` |
| No manifest record has the requested source ID | Reject a record outside the authorized set. | An extra space in an ID. | Ledger / `reserve` |
| Parsed last user-message content is not equal to `{"text": record["text"], "star_rating": record["star_rating"]}` | Reject changed/truncated text, changed rating or additional input fields. This is Python equality after JSON decoding, not raw JSON-byte comparison. | Trimming whitespace from the original review or adding an unused field. | Ledger / `reserve` |
| Ledger path missing or not absolute | A persistent, explicitly located attempt ledger is required. | A relative path to the same intended file. | Ledger / `connection` |
| Stored manifest digest exists and differs from SHA-256 of the current records serialized with `sort_keys=True, ensure_ascii=False` | A ledger cannot be reused for changed input records. | Reordering the record list or altering whitespace inside review text changes the digest; dictionary key order does not. | Ledger / `reserve` |
| Ledger `control` contains `stopped` | An earlier shared configuration error stopped subsequent paid attempts. | None; manual retry is not authorized by clearing the flag. | Ledger / `reserve` |
| An `attempts` row already has this source ID | Each approved review gets at most one reservation. | Duplicate task delivery, including after an interrupted first attempt. | Ledger / `reserve` |
| Attempt count is at least 6 | Maximum paid-attempt budget is exhausted. | None. | Ledger / `reserve` |
| SDK raises any exception | Current reserved attempt fails; fallback, no SDK retry (`max_retries=0`). Ledger stores exception class and HTTP status. | A timeout may occur after the provider has already processed a request. | Provider / `OpenAIProvider.complete`; Client / `categorize_apartment_feedback` |
| SDK exception is `AuthenticationError`, or its status is 400, 401, 403 or 404 | In addition to current fallback, write shared `stopped` flag to block future reservations. Other statuses do not set this flag. | A valid key without model permission; a bad request parameter. | Provider / `OpenAIProvider.complete`; Ledger / `finish`, `reserve` |
| Any other `Exception` inside the client's `try` | Initialization, manifest file/JSON/key errors, SQLite errors, malformed provider response, response serialization, or audit-writing errors also produce a failed audit and fallback. | Missing response choices; an unavailable ledger filesystem. | Client / `categorize_apartment_feedback`; Provider / `OpenAIProvider.complete`; Ledger / `connection`, `reserve`, `finish` |

The generic catch records `ValueError`/`ExperimentBlocked` messages; other errors
are recorded as class plus HTTP status. There is no additional semantic repair.
Imports, input validation and request construction precede that catch. Errors
there, errors while computing keyword fallback, and database commit failures can
fail the task instead of producing a saved fallback. If the provider returns but
ledger response-writing or response conversion fails, the reserved call remains
consumed; raw output may be absent from the saved audit. No claim is made that
logging can succeed when its own persistence fails.

## CSV and persistence gates before analysis

All CSV rows are validated before the import loop, but database writes are committed
per row. A later plan-capacity or database error can leave a partially imported
batch. These are import/storage failures, not failed AI interpretations.

| Exact condition | Meaning | Outcome / scope | Harmless-looking example | Source / function |
| --- | --- | --- | --- | --- |
| Filename does not end with lowercase `.csv`; no CSV headers; no recognized text column | Wrong upload shape. | HTTP 400; reject whole upload. | `reviews.CSV`; a nonstandard text-column name. | API / `import_csv` |
| UTF-8 decoding, CSV parsing, file reading or dependency/database access raises | Input or infrastructure cannot be read. | Request error; no automatic analysis fallback. | A CSV in a different character encoding. | API / `import_csv` |
| Plan has a limit and `usage.feedback_count >= limit` | Import capacity exhausted before processing. | HTTP 402; whole upload rejected. | None. | API / `import_csv` |
| Current organization ID string differs from experiment organization environment value | Upload must belong to the isolated organization. | HTTP 400; whole upload rejected. | `"01"` versus `"1"`. | API / `import_csv` |
| `len(rows) != 6` | Exactly six rows are required. | HTTP 400; whole upload rejected. | An additional nonblank data row. | CSV / `validate_rows` |
| Row key set differs from `text`, `star_rating`, `source_external_id`, `source`, or any value is `None` | Require normalized columns and present cells. Empty review text is permitted. | HTTP 400; whole upload rejected. | An extra unused column or missing trailing cell. | CSV / `validate_rows` |
| Source ID empty, longer than 255 characters, or repeated within upload | Require usable unique mapping. | HTTP 400; whole upload rejected. | An accidentally repeated row. | CSV / `validate_rows` |
| Rating string not one of `"1"` through `"5"` | Normalized CSV needs integer rating strings. | HTTP 400; whole upload rejected. | `"4.0"` or `" 4 "`; the separate preparation script accepts/normalizes these before upload. | CSV / `validate_rows` |
| Source not one of the two exact experiment source names; or more than one source used in a batch | Require separate AI and comparison imports. | HTTP 400; whole upload rejected. | Source capitalization/spacing difference. | CSV / `validate_rows` |
| AI-source batch and organization AI disabled | Do not silently run an intended AI batch as fallback. | HTTP 400; whole upload rejected. | None. | API / `import_csv` |
| Existing row with same organization, source and external ID | Duplicate import prevention. | HTTP 409; whole upload rejected before writes/queueing. | Reuploading an identical CSV. | API / `import_csv` |
| During loop, limited plan and `total_used + imported_count >= limit` | Remaining rows exceed capacity. | Reject affected rows; previously imported rows stay and are queued. | None. | API / `import_csv` |
| Exception creating/committing/refreshing a row | Row could not complete import. | Record row error and rollback current transaction; earlier commits remain. | None. | API / `import_csv` |
| Non-null `star_rating` violates `BETWEEN 1 AND 5` | Database rating constraint. | Reject database write, not one AI field; no model fallback. | None. | [migration](../../services/backend-api/alembic/versions/b8a4029c7d10_add_apartment_review_analysis.py) / `upgrade` (`ck_feedback_star_rating`) |

Ordinary authentication dependencies also gate upload: HTTP bearer credentials,
successfully decoded access token with a `user_id`, an existing non-deactivated
user, and access to its organization and usage record.
They fail the request, not an AI result; see API
[`dependencies.py`](../../services/backend-api/src/api/dependencies.py),
`get_current_user`, `get_current_org`, `get_current_usage`. They are not new AI
validators. Broker publication failure in
[`queue_analyze_batch`](../../services/backend-api/src/background/celery_client.py)
raises after import; imported rows can remain without a queued job. Worker database
commit errors likewise prevent durable results; they do not authorize another paid
request. The ledger remains the attempt authority.

## Fallback-only behavior, warnings and non-runtime checks

| Condition | Actual consequence / scope | Source / function |
| --- | --- | --- |
| Keyword occurrence is wholly contained in a configured excluded phrase | Drop that occurrence only; another valid occurrence can still create the topic. No whole-analysis rejection. For example, `security` inside `security deposit` is excluded. | Contract / `keyword_result`, `pattern`, `EXCLUSIONS` |
| No valid keyword occurrence for a topic | Omit that topic. No matches anywhere produces `topics=[]`; no rejection. | Contract / `keyword_result` |
| `not text.strip()` | Use rating mapping without invoking the sentiment engine; empty topics. | Contract / `keyword_result`, `rating_sentiment` |
| Sentiment-analyzer construction raises inside the constructor guard | Log warning and try default VADER construction. If that also fails, the task can fail; it is not another AI attempt. | Worker / `get_sentiment_analyzer` |
| Sentiment provider `.score(text)` raises | Log warning and call fallback VADER scoring; only sentiment computation changes. In this experiment VADER is already selected. | Sentiment / `SentimentAnalyzer.analyze` |
| Fallback sentiment `.score(text)` also raises | Log error and use fixed scores with compound 0, producing **neutral** overall sentiment. Keyword topics survive. | Sentiment / `SentimentAnalyzer.analyze` |
| Compound score ≥ 0.05 / ≤ −0.05 / otherwise | Label positive / negative / neutral; this is a classification rule, not an acceptance check. Topic sentiments remain unknown. | Sentiment / `SentimentAnalyzer._classify_label`; Contract / `keyword_result` |
| Cache invalidation raises after analysis | Warning only; does not invalidate the saved analysis or trigger AI fallback. | Worker / `_invalidate_org_cache` |

`topic_sentiment_limitation` and the successful-validation message requesting human
review are informational, not rejection gates. No mixed-evidence quality check,
topic-coverage score, keyword-to-AI agreement rule, or warning-to-fallback rule exists.
Normal software classifiers, urgency/risk/actions, secondary providers and scheduled
AI jobs are bypassed/disabled in this scoped mode; their ordinary checks are not
apartment-response validators.

Separate tools/tests must not be confused with runtime rejection:

- [`prepare_input.py::prepare`](prepare_input.py) checks six unique requested IDs,
  unique/present source headers, exactly one source occurrence per ID, present
  text/rating cells, accepted numeric rating strings, and a new output directory.
  Failure stops private input preparation; it does not reject a model response.
- [`export_results.py::export`](export_results.py) checks the manifest/ledger and
  reports missing/duplicate saved records, exact input readback, parsed-versus-saved
  agreement and sentiment-column agreement. CLI checks also enforce the expected
  isolated organization and one result page. These checks do not alter saved
  analysis, trigger fallback or rerun AI. Structural export errors can stop export.
- [`test_contract.py`](test_contract.py), [`test_normalization.py`](test_normalization.py), [`test_worker.py`](test_worker.py),
  [`test_startup.py`](test_startup.py), and [`check_pipeline.py`](check_pipeline.py)
  are offline development checks with fictional data/mocked provider transport.
  They are not runtime filters and do not prove correctness on every possible input.

Private reports and logs are separate review artifacts. This document contains no
real review identifiers, review text, credentials or identifiable test output.
