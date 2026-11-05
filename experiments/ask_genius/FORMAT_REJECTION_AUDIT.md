# Ask Genius response audit — November 5, 2026

Status: implemented on the PR #12 branch; live acceptance pending. Not merged or deployed.

## What was inspected

Traced the Ask Genius workflow through browser input/API client, authenticated question route, period/source/type resolution, original-survey evidence preparation, prompt and example loading, model request adapter, response schema, parser, reference validation, answer persistence, history/follow-ups, private/public chat rendering, sharing snapshots, and the portable test runner. Searched the application for rejection and limit rules; read the relevant implementations. This is an audit of the application's Ask Genius path, not a claim to have reviewed every unrelated product feature or third-party dependency. No production runtime or browser session was accessed in this audit.

Primary files: `src/services/ask_genius.py`, `ask_genius_surveys.py`, `ask_genius_periods.py`, `ask_genius_followups.py`, `ask_genius_sharing.py`, main instructions/example bank; `src/api/routes/ask_genius.py`; `src/models/conversation_message.py`; frontend `AskGenius.tsx`, `GeniusMessage.tsx`, `GeniusSurveyEvidence.tsx`, `SharedGeniusChat.tsx`, `lib/api/ask-genius.ts`, `lib/api-client.ts`; `experiments/ask_genius/round2_acceptance/*`.

## Remove or recover unnecessary rejection rules

| Rule found | Why it can reject a usable answer | Implemented correction |
| --- | --- | --- |
| Findings must use one exact field name | Three real responses copied the input flag name onto the findings list. | Recognize that observed alias only when it contains a list. Conflicting values still fail. Clarify the input flag versus response field in the contract. |
| Finding references must have nonempty answers | “No comment submitted” can accurately refer to an unanswered optional question. | Allow references to any original question in that submission. Do not create a resident answer. |
| Survey excerpts match stored codes only | Displayed choices and numeric rating labels are supplied to the model but were rejected as quotations. | Match the actual selected answer's original code or display label, bound to the cited question. Unselected choices still fail. |
| Ordinary explanation must fit 1,000 characters; expanded answer 3,000 with special quote arithmetic | The storage and chat renderer have no such display restriction. Correct qualifications can exceed it. | Keep concise writing targets; remove those hard rejections and quote-length arithmetic. Log target overruns, preserve complete prose. Retain a 20,000-character resource ceiling. |
| Findings have a hard 300-character ceiling | Slightly longer notes can preserve relevant distinctions. | Keep 300 as a prompt target, with a generous 2,000-character resource bound per note. |
| Any URL, Markdown link or HTML-like text rejects the answer | The actual private and shared chat renderer already disables navigation, images and raw HTML. | Let that renderer handle inert markup. Record its presence. Model prose never grants a source link or action. |
| Null optional lists / blank optional selectors / redundant missing survey kind | These can express the same absence or an unambiguous survey reference. | Normalize null optional lists to empty; blank optional fields to absent; infer survey kind only when survey_id exists and review_id does not. Validate afterward. |
| Repeated identical findings/question references | Redundant identical references add no new meaning. | Deduplicate exact copies. Conflicting findings and foreign references still fail. |
| Survey topic label forbids Markdown characters | Topic is a display label; React renders it safely and unmatched groups remain available. | Remove the character blacklist and use the same 500-character label bound as reviews. |
| Refusal appears as an empty/format failure | The manager is sent down the wrong troubleshooting path. | Distinguish provider refusal from empty, unfinished and invalid output; retain raw response. |

Existing safe fence and literal-newline handling is retained. All normalization operates on a copy; raw provider outputs remain unchanged. No silent answer truncation or automatic paid retry.

## Retain consequential checks

| Check | Reason to retain |
| --- | --- |
| Organization, personal-conversation and source ownership | Prevent another property's or person's records from entering the request, popups or shared snapshots. |
| Finalized surveys, resolved period and explicit type scope | Drafts are not submitted feedback; changing scope changes the answer. |
| Unknown source/question IDs, mismatched quotations and saved-analysis topics | These create false supporting evidence. Do not invent replacements or silently discard them. |
| Every supplied survey represented in a required coverage pass | The fourth real failure omitted three surveys and falsely denied unresolved issues. This check caught a consequential omission. It does not prove semantic accuracy. |
| Conflicting duplicate JSON fields or findings | Choosing a value would guess at meaning. Exact duplicates in finding lists can be normalized, contradictory ones cannot. |
| Unknown structural/filter fields | Dropping a misspelled filter can broaden results. No generic “ignore all unknown fields” policy. Recover known unambiguous variations instead. |
| Correct field types, bounded list sizes, nonempty final prose | Keep the output interpretable and bounded; do not display serialized objects as an answer. |
| Unfinished output, missing response, provider errors | A truncated or absent answer must not appear complete. Refusals now have their own diagnosis. |
| Idempotency and one question at a time | Prevent duplicated paid requests and inconsistent history. Explicit Retry after a recorded failure remains available. |
| Raw-data and prompt audit | Needed to distinguish application rejection from incorrect model content. Never erase failed attempts. |
| Public-share allowlist and size bounds | Prevent leaking tokens/private metadata or unexpectedly publishing additional data. |

## Other application limitations found, not response-format failures

- At most 100 reviews / 100 surveys and 80,000 serialized evidence characters. Oversized cohorts are rejected before a model call instead of silently trimmed. This needs a future scale design; removing the check alone would make incomplete answers more likely.
- Explicit period choices and conservative date parsing sometimes require clarification. Unsupported/ambiguous date requests must not silently reuse an old period.
- Source/type “or” choices can ask for clarification. Broad/narrow scope is significant, not cosmetic.
- Some precise count questions are answered locally; unsupported count conditions return a limitation. The existing maintenance-only resolution summary must never be interpreted as all-survey unresolved-issue coverage.
- Review source-only follow-ups use a narrow local shortcut. If its bullet/history/length rules do not match, the request falls back to the model; it does not reject a completed model answer.
- Browser input caps questions at 2,000 characters; backend accepts 4,000. Neither limits answer display. This is not implicated in the five failures.
- History supplies the last ten messages; failed attempts are excluded. The reviewed five-call run had no successful assistant history before Q3, so its omission cannot be blamed on inherited earlier answers.
- Provider timeout is 45 seconds; configured output allowance is 1,200 tokens plus 160 per survey for broad checks. All five reviewed responses finished normally well below the allowance. No evidence supports increasing these limits for this failure.

## What the paid evidence proves

Original archive: `Ask-Genius-Results-20261105T211225527103Z.zip`. Five real model calls; four application rejections, one accepted but incomplete answer. 66,449 input tokens and 1,859 output tokens; price unavailable. No new paid requests occurred during this audit.

| Original question | Old software result | Replay after corrections | Factual assessment of original prose |
| --- | --- | --- | --- |
| Bad surveys, sequential | Rejected structure | Accepted with field-name normalization | Still wrong/incomplete: misleading count and missing departure reason. |
| Improvements | Rejected structure | Accepted with field-name normalization | Retains the three main concerns; ancillary notes still overstate absence of unresolved issues. |
| Overall assessment, sequential | Accepted | Accepted | Still omits the departure reason and overstates absence of issues. |
| Bad surveys, fresh | Rejected coverage | Still rejected coverage | Missing fob/departure concerns; denial of unresolved issues is false. |
| Overall assessment, fresh | Rejected structure | Accepted with field-name normalization | Final prose broadly retains the four submissions; note/question mapping remains imperfect. |

These are replays of existing strings, not improved fresh model answers. Source membership and coverage checks cannot establish that a summary is factually complete. The full historical requests and responses remain in the original evidence record; the repository fixture stores original evidence and raw response objects for regression replay.

## Factual correction and next test

Clarify that a selected actual departure reason matters even alongside favorable scores and blank comments. No optional comment is not proof of no concern; an unasked resolution question is not evidence of resolution. Keep future renewal criteria separate from actual reasons for leaving. Preserve all previous examples and add Example 9 with the actual incomplete answer, assessment, suggested answer and complete original questions.

Run the same five-question focused diagnostic on the same four finalized submissions. No new emails, survey edits, model/provider change or automatic retry. It must retain the missing second fob, rude-but-resolved repair, community-conditions departure reason, and renewal factor without inventing a specific noise/parking cause or unfair-price complaint. Review both sequential and fresh answers, supporting references, all raw failures and usage. Stop at five and assess the results.

Because Example 9 uses this same cohort, this is a regression test, not a blind generalization test. It cannot alone establish reliable behavior on new properties or unseen surveys. Software success and human factual acceptance remain separate.

## Software verification

Full backend offline suite: **336 passed**. Actual private/shared chat renderer tests: **25 passed**. The first backend attempt had 324 passes and nine failures from stale assertions, a package built from the prior committed tree, and changing the bank during test collection. Those test/setup issues were corrected before the complete successful rerun; both logs and captures are retained. Existing datetime deprecation warnings remain. These tests use fake providers or replay saved outputs; they are not new paid model answers or human factual acceptance.
