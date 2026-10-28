# Ask Genius: approved MVP behavior

Approved with the product owner on 27-28 October 2026, including the reviewed
four-page visual sketch and public-sharing decision. This increment improves the
existing chatbot; it does not re-run review analysis or add a new agent framework.
The executable assistant instructions live in
`services/backend-api/src/services/ask_genius_instructions.txt`.

## Starting and continuing a conversation

- Require an explicit period before asking unless the manager has explicitly
  saved a default. Keep the current conversation's period across follow-ups.
- Offer the past 7, 14, or 30 days, last calendar month, last calendar quarter,
  last six months, year to date, a custom date range, and all available history.
- Save/clear a default for the signed-in account only after an explicit request,
  including a clear natural-language request in chat. Ordinary period changes
  affect the conversation, not the account preference. Relative defaults roll
  forward with the application's current date.
- Filter before sending records to the model. Use original review dates;
  never substitute import timestamps. Explain missing-date coverage. Selecting
  all available history is an explicit choice, including for the undated pilot.
- Broad requests may need one clarification about time, topic, source, or focus.
  Reuse established context and accept an overall summary as a valid scope.

## Opening questions

Show these four starters after the period control. They remain readable and
clickable before a period is selected. Selecting any question fills the editable
composer; only sending starts an answer request. If a period is missing, clearly
direct the manager to the selector rather than making the question cards inert.
Keep the orange missing-period cue visible after focus moves to the composer;
clear it only once a valid period is selected, including complete custom ranges.

1. Which topics came up most often in reviews during this period?
2. What were the main complaints in reviews during this period?
3. What did residents praise in reviews during this period?
4. How many reviews did we receive at each star rating during this period?

"Browse more questions" opens a compact tabbed panel. Reviews covers original records
and basic counts; Analysis covers saved subjects, sentiment, and patterns.
Browsing does not call a model. Reviews, Analysis, Surveys and Management
responses are all visible. Disconnected categories say "Not connected yet";
their questions cannot be submitted. This increment does not connect new sources.

The sole approved future Management responses question is:
"What follow-ups did we promise residents in management responses during this
period?" It identifies recorded promises; it does not establish completion.
Do not include the rejected question about concerns left unanswered in replies.

## Answering and evidence

- Across conversations, lead with relevant complaints, negative feedback and
  concerns, giving them greater emphasis. Include positives afterward only when
  the question calls for them or they are necessary for an accurate answer that
  avoids a misleading impression. Respect positive-only requests; never invent
  or exaggerate concerns or expand beyond the question's scope.
- Lead with the finding. Include verified counts when relevant, including in
  initial complaint summaries. Explain overlap when reviews address several
  concerns. Reviews are not unique residents; ratings and sentiment are distinct.
- Use bullets for two or more distinct findings, short paragraphs for a single
  explanation, and blank lines between paragraphs and lists. Use numbered lists
  for ranked priorities and explain the ranking with supported seriousness,
  frequency and reliable recency. Avoid repetition, filler conclusions and
  unnecessary staff or reviewer names. Avoid a fixed report template.
- Follow-ups retain the same topics, source scope and established timeframe.
  Resolve this scope before selecting a presentation. After negative-topic
  discussion, "let me see each review" retains those topics and negative content,
  with sources grouped beneath each topic. It does not reset to every review in
  the period. Explicit broadening replaces only the restrictions the manager changes.
  Attribute claims to residents instead of presenting them as proven facts.
  Missing dates or resolution records do not establish a current/unresolved
  problem. For undated all-history data, say "across the saved reviews" rather
  than implying a complete community history or dated intake count.
- Maximum 1,000 characters, including spaces, for summaries and explanations.
  Requested source detail written in the answer may expand it to 3,000 characters;
  the explanatory prose itself stays within 1,000. A citation or headline count alone does
  not qualify for the larger limit. Never cut a qualification or sentence away
  to make an oversized answer appear compliant.
- Show evidence when requested or after the manager accepts an offer. Select by
  relevance, then reliable recency, including contrasting evidence when material.
  No fixed number of excerpts. Use View review / View N reviews links under the relevant topic,
  not internal labels such as "Review 3" or long source cards. Open the full review and expandable
  saved analysis in a popup without leaving the chat. Full popup contents are
  separate from the displayed chat-answer character budget. Provide requested
  evidence directly without offering it again. Provide author
  information only if requested and actually available.
- Read community information only. No publishing, contacting residents, tasks,
  source-record changes, or implied actions. Personal chat management, explicit
  sharing and the requesting manager's default preference are application
  controls, not model-granted permissions.

## Visual design and chat controls

- Preserve BoomSay's warm theme, make the period selector prominent, keep saving
  a default secondary, and condense the missing-date notice.
- Larger, darker text and a shared central column for messages and composer.
  History stays visible; no collapsible history sidebar in this increment.
- Use "New chat" and "Your chats". Keep automatic names or allow a saved custom
  name. A three-dot menu provides Rename, Pin/Unpin, Share and Delete. A pin icon
  also toggles pinning; pinned chats appear first. Confirm deletion.
- Show Answering while awaiting a response; attach Retry to a failed question
  and keep its text visible. Copy appears beneath a completed answer. Diagnose
  repeated failures, not just their generic error text. No automatic paid retry.

## Public sharing

Share creates and copies an unguessable public link to a read-only snapshot.
Anyone with the link can view it without a BoomSay account. Confirmation:
"Link copied. Anyone with the link can view this chat."

Only that conversation and its selected supporting review/analysis content are
shared, including the evidence popups. Other chats, the dashboard, raw provider
payloads, credentials and unrelated community data are excluded. Later messages
do not automatically change an existing snapshot. Manage link and link
deactivation are explicitly deferred. Share does not send messages to recipients.
The current loopback-only Mac preview can demonstrate this in a signed-out
browser on the same Mac; remote recipients require a reachable hosted instance.

## Verification and release

Test full multi-turn conversations and source popups, private chat ownership and
pin/rename/delete persistence, anonymous snapshot isolation and immutability,
date boundaries and missing dates, calculated cohorts, preference persistence
and ownership, explicit versus temporary changes, request replay, source links,
answer limits, responsive rendering, and the browser-to-API flow. Automated model
responses are simulated and must be labeled as such. No paid model tests are
authorized by this implementation exercise. Real answer quality remains for the
manager to assess in the configured Mac preview.

Push the completed changes together to the existing Ask Genius draft PR. Do not
merge or deploy production. Supply the compatible Mac source update while
preserving credentials, login, database, and blocked review-analysis settings.

## Approved review-links follow-up

- Share confirmation: top-center highlighted green banner, white text, checkmark,
  close button; no Manage links option.
- Supporting-review follow-ups preserve concise topics and order, attach each
  topic's validated reviews directly beneath it, and do not offer evidence again.
- Direct review lists give the count once and open all matching records in a popup,
  up to 50 per displayed evidence message. Further pages are manager-triggered,
  preserve filters/order, do not repeat reviews and require no model call.
- Character limits apply only to LLM-written messages, excluding popup reviews,
  popup analysis and application-generated controls. No longer topic explanations
  were requested; that earlier interpretation was withdrawn.

## Consolidated instruction policy

Maintain one behavioral policy, with the runtime contract limited to data and
output fields. Integrate refinements into the relevant rule, replacing superseded
wording. Use a small set of distinct illustrative examples, never production facts.
For frequency questions, retain frequency order and give each topic its own bullet,
verified count and actual reported experience, complaints first within the topic.
Do not substitute sentiment labels for substance or broader-topic counts for a
narrower complaint. Context, counts and source mappings must agree.
