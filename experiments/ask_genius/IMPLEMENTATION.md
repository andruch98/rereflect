# Ask Genius — Lake House pilot

Approved scope: answer questions about the selected Lake House community's saved
reviews and saved apartment analyses. Reuse the existing chat presentation and
history. Ask Genius is the landing experience; Reviews remains available.
Replies, surveys, tasks, citations and portfolio comparisons are deferred.

## Implementation decisions

A fixed authenticated read/calculation/answer flow is used. The six saved review
records are not reanalyzed. The model receives original statements separately
from saved interpretations and code-calculated counts. Review records are not
unique-resident counts, nor proof of the community's entire history. Missing
posting dates cannot support trends. Mixed topics preserve quotation sentiment;
a rating-only review provides no written reasons.

Source records cannot be changed through this path. The only writes are the
user's conversation, answers and internal request/usage history. No SQL generator,
action executor, web search, response publisher, or analysis worker is used.
Standard counts are calculated in code; unsupported filtered calculations must
be acknowledged, not improvised. This is deliberately a small bounded pilot,
not an arbitrary analytics engine.

## Course basis and judgment

The team read all three original course sources in full before establishing
this implementation approach (Deep Agents was divided across three readers).
Relevant original passages were also inspected directly by the lead reviewer.

- LangGraph M1 L1 (source lines 92–98): fixed chains execute the same steps;
  increased model control has reliability trade-offs. Our judgment: use a fixed
  sequence rather than a new autonomous agent framework for this increment.
- LangChain 2.2 Custom state/context (source lines 441–455): give the model only
  needed information; runtime context is immutable. Our judgment: authenticated
  community and user identity belong in server code, not model-selected fields.
- Deep Agents M2.2 (line 5927): permissions are enforced in code, not prompts.
  The actual API must enforce access even if user/review instructions disagree.
- Deep Agents M2.4 (line 7402): code is more reliable for grouping/counting than
  model arithmetic in prose. No interpreter or shell is needed for these counts.
- LangGraph M2 L3 (lines 500–504): internal state can be broader than returned
  answers. Evidence is retained internally while visible citations stay deferred.
- Deep Agents M4.1 (10155–10157): simple single-step tasks do not justify subagent
  overhead. Our product does not acquire a multi-agent design from this work.

These are course principles and our implementation judgments, not a claim that
historical course API details were used as current SDK documentation.

## Live verification boundary

The isolated Mac preview has no configured chat model/credentials and no API
internet egress. The model-selection question returned no selection. No provider
or model choice is inferred from a past experiment. Simulated responses test
software plumbing only; they do not establish factual quality of live answers.

Before live validation, select a provider/model and configure its credentials and
API-only egress in the isolated preview. Preserve the blocked review-analysis
ledger, stopped workers and private database. Never ask the user to paste keys
into chat. Do not modify production services to enable a test preview.

Bounded live acceptance set: praise, complaints, Mixed staff feedback, rating-only,
counts, follow-up, missing dates, another-community request, requested action and
instructions embedded in review text. Record every request/output/failure plus
human factual assessment and available usage. This live evaluation is pending.

## Configuration and implementation limits

The feature is off unless ASK_GENIUS_ENABLED=true. Explicit ASK_GENIUS_PROVIDER
and ASK_GENIUS_MODEL are required; no default model or production key is inherited.
The existing SDK adapter supports openai, openai_compatible and ollama. OpenAI
requires a separate ASK_GENIUS_API_KEY and uses its explicit official endpoint.
Compatible/local endpoints require ASK_GENIUS_BASE_URL. This is an implemented
adapter boundary, not a recommendation to choose one vendor over another.

The dataset is bounded at 100 saved imported review records and 80,000 evidence
characters, with no silent sampling. The model receives at most 10 prior messages.
One request has a 45-second timeout, 1,200 completion tokens and no automatic
retry. Only supplied code aggregates may be used as exact counts; arbitrary
subset calculations are not implemented in this increment. No embeddings,
vector database, autonomous tools or new agent framework were added.

History reuses existing Conversation/Message tables with a dedicated scope,
creator and organization checks. Legacy chat/list/detail/action paths exclude
this scope. Request IDs prevent duplicate generation after uncertain failures.
Known failed attempts require a new explicit attempt; automatic retries are off.
PostgreSQL uses a session advisory lock to reject concurrent submissions; the
SQLite test harness exercises the process lock instead.

## Verification status

- 51 distinct focused frontend checks passed (46 chat/layout/answer regressions
  plus 5 middleware landing checks). Full TypeScript retained the same 87 existing
  diagnostics; none added. ESLint had no errors.
- 17 backend checks passed against an isolated SQLite database using real
  auth/routes/models and simulated model responses. Includes exact prepared
  evidence from all six original saved reviews. No source records reanalyzed.
- Actual saved-data aggregates: 6 records, 5 written, 1 rating-only, all 6 original
  posting dates unavailable; 3 positive and 3 negative overall; average 3.1667
  stars, 3/6 high-star reviews (50%). Staff occurs in 4 records, with praise in
  3 and criticism in 2 when mixed quotations are counted by record.
- Live model response accuracy, provider connectivity, PostgreSQL advisory locks
  and full Docker startup remain unverified. Actual model requests: zero; no
  actual model tokens or charges incurred. Mock token fields are synthetic.
- Initial frontend checks failed before an empty-state fix; the full first log
  was overwritten. The run-history record discloses that missing capture and
  preserves the available excerpt. Browser inspection also found a remaining
  middleware redirect to Reviews; the preview redirect was corrected and five
  focused entry-path checks added.

Software checks are not a human approval of factual model outputs. Complete
mocked inputs/outputs and simulated failures are in the private downloadable
verification record, outside Git. Human/live answer assessment remains pending.

Final browser replay passed: default Ask Genius landing, honest unconfigured
state, no automatic question requests, starter selection, one simulated answer,
history reopening without regeneration, mobile layout and centered review cells.
Screens were visually inspected. The run used mocked API responses and fallback
fonts, not the live database/provider. Earlier browser attempts found the landing
redirect issue, then required test-harness viewport correction and a fresh dev
cache after interrupted compilation. These attempts are disclosed in the bundle.
