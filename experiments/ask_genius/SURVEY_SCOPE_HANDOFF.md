# Survey corrections — combined PR #12

November 5, 2026 (America/New_York). Branch `fix/ask-genius-survey-selection`,
stacked on `feat/lifecycle-email-preview` (#11). Implemented in this PR;
not merged, deployed, or installed on the user's Mac. Human answer-quality
acceptance remains pending. Property naming remains separately queued.

## Next action: four new submissions, terminal acceptance test

The user submitted `nov5-maintenance-1`, `nov5-maintenance-2`,
`nov5-pre-renewal` (9-month) and `nov5-move-in` on November 5. Prepared
`experiments/ask_genius/four_survey_acceptance/` for 14 sequential questions:
12 in one new chat, plus independent negative-feedback and overall summaries.
It runs the unchanged application source at `ddc0b2cb2dbeca7f7fc245881cd7ae87ef50987c`
with the user's configured model. Only the four named finalized fictional
records are read, in a read-only transaction; all route writes use an ephemeral
SQLite copy. No preview installation, source-record changes, emails or shares.
Capture full original evidence, actual messages/raw responses, tokens,
validation errors and human-assessment placeholders. Stop at the first failure;
no retry. At most 14 model calls (13 in the simulated full run; count is local).

Fresh verification: 11 diagnostic tests passed, including packaged source with
a local fake HTTP provider, original database unchanged, old-record exclusion,
follow-up history/fresh chats and first-error stopping. Full backend Ask Genius
offline suite: 279 passed. No live model calls; simulated usage is not actual
cost. Initial fixture/assertion failures and a local test-runtime SOCKS dependency
failure are retained/disclosed in the downloadable package's verification record.
Docker/Mac execution and human factual accuracy remain unverified here.

Next: Andres runs the package once and returns its results ZIP. Assess against
these four originals, including historical-example leakage and history effects;
do not call this a paired old/new comparison. Normal browser Share/source-popup
checks and review/mixed regression checks remain separate acceptance work.

## Current additions

### Approved survey examples

The entire approved five-example Markdown file is read at application startup
and included verbatim once in every Ask Genius model request, including review
and mixed-source requests. There is no example selection, summarization,
retrieval service, extra model call, or new dependency. Locally calculated
answers still need no model request. Restart/rebuild loads file changes.

- Main instructions: `services/backend-api/src/services/ask_genius_instructions.txt`
- Approved bank: `services/backend-api/src/services/ask_genius_survey_examples.md`
- Assembly and unchanged output contract: `services/backend-api/src/services/ask_genius.py`

Section 6 contains the agreed scope rule: review-only questions must ignore the
survey examples; mixed questions apply them only to the survey portion.
Example facts never supply current community evidence. The bank stays outside
the authorized-evidence message and stored source records. Its introduction,
five examples and complete source-question appendix match the approved file
byte for byte. The redundant short survey-count example was removed from the
main prompt; the distinct source-popup example remains. The complete prompt,
examples and output contract were reviewed together for conflicting scope,
format and evidence instructions.

This deliberately increases request context, including for reviews. Extra token
usage, cost and answer-quality improvement have not been measured. The model,
provider, generation settings, current evidence, history policy and validators
are unchanged. Inclusion and software checks do not prove the model will follow
the examples or ignore them correctly on reviews.

### Share survey conversations

The existing Share action now works for survey-only and mixed conversations,
including older chats carrying the obsolete sharing-block metadata. Like review
shares, each action creates a frozen read-only copy accessible to anyone with
the link. Later messages, edits, or deleting private history do not change that
copy. Existing review shares remain compatible. No links were published to real
conversations during implementation.

Attached survey sources are rebuilt from owned, finalized original submissions.
The snapshot contains their title, type, original question text and displayed
submitted answers, preserving the topic and selected-question relationship.
Each submission receives a snapshot-local ID. It excludes resident/contact/unit
metadata, private survey tokens, live record IDs/links, drafts, raw model payloads
and unattached records. Resident wording or manager chat text may itself contain
personal information: this feature is not a redaction service. As with review
shares, the manager chooses which conversation to share.

The shared page opens the relevant answers first, with the existing option to
view all answers from the same submission. It never fetches authenticated survey
records, including when snapshot answers are missing. Ownership checks, snapshot
size limits and existing public-link protections remain in force. No migration
or existing-record rewrite is required. Link revocation remains outside this
existing sharing MVP.

## Earlier work retained

- Named questionnaire requests switch type; broad unqualified survey evaluations
  reset to all types within the chosen period; short follow-ups retain subject.
- Question-specific rating counts and integrated evidence instructions preserve
  low aspect ratings, unresolved issues and reported safety concerns.
- Model-facing survey evidence removes repeated context/question wording while
  preserving every answer, choice, label, scale, original source and count.
- Sent/simulated/unconfirmed/failed/opted-out invitations remain distinct from
  submitted feedback. Provider acceptance does not prove inbox delivery.
- Blank forms no longer claim a saved draft; reopen/save/edit/failure handling
  remains intact.

The user's private captures showed all nine submissions and 36 answers reached
failed broad summaries. Missing retrieval did not explain those omissions. A
fresh-chat summary also omitted poor move-in condition, so chat history alone
was not a sufficient explanation. The earlier 24.0–24.3% character reduction
measured evidence simplification only; it does not describe this larger prompt.

## Verification for these additions

- Ask Genius offline backend suite: **268 passed**, with simulated model outputs.
  Includes review/survey/mixed request construction and follow-ups, all seven
  questionnaire types, legacy chats, frozen shares, ownership, forged metadata,
  invalid source references, draft/foreign exclusion and existing review shares.
- Frontend reviews/surveys suite: **158 passed, one existing skip**. After a final
  test-only TypeScript correction, the affected Ask Genius suite passed again
  (**34 tests**, included in the total above).
- Affected-file ESLint passed. Git whitespace checks passed.
- Full frontend TypeScript: **87 errors**, byte-identical to a fresh check of the
  unchanged local baseline. This is not a passing project-wide typecheck.
- Initial test invocation used the wrong working directory and collected no
  backend tests. The first frontend run had one obsolete assertion that public
  survey sources must remain hidden; updated for the approved sharing behavior.
  Two TypeScript errors in a new test used an unsupported query option; corrected.
  Attempts, complete available simulated requests/outputs, expected validation
  rejections and assessments are preserved in the private test record.

No live Ask Genius or judge requests were made; fixture token counts are not
actual usage. No provider cost was incurred by these offline tests. Tests establish
software behavior, not human judgment of factual accuracy. Browser-level visual
inspection and live-provider behavior are not captured in this addition.

## Next action and bounded acceptance

Prepare a guarded local preview update from this PR before the next acceptance
run. The older evidence-only comparison package must not be reused as though it
tests these examples: it intentionally requires unchanged instructions.

Bound the next live evaluation to at most eight requests on the same configured
model: three previously failed survey questions, two unseen synthetic survey
cases with changed facts, one review-only question, its short follow-up, and one
mixed-source question. Fix the evidence and expected findings before running;
retain complete requests, outputs, provider usage/cost when supplied, validator
results and human assessments. Stop on the first request/validation error; no
hidden retries or judge calls. Stop and diagnose the first factual failure.

Check omissions, invented causes, correct low-rating/unresolved criteria,
review/survey separation and no fictional example facts entering real answers.
Separately test Share and source popups in the normal UI with a synthetic chat.
Approval of example content is not acceptance of live model quality. Merge and
deployment still require explicit authorization.
