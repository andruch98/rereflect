# Ask Genius: approved MVP behavior

Approved with the product owner on 27 October 2026. This increment improves the
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

Show these four starters after the period control. Selecting any question fills
the editable composer; only sending starts an answer request.

1. Which topics came up most often in reviews during this period?
2. What were the main complaints in reviews during this period?
3. What did residents praise in reviews during this period?
4. How many reviews did we receive at each star rating during this period?

"Browse more questions" opens a curated menu. Reviews covers original records
and basic counts; Analysis covers saved subjects, sentiment, and patterns.
Browsing does not call a model. Categories reflect connected sources only.
Surveys and Management responses remain hidden until their data is connected.

The sole approved future Management responses question is:
"What follow-ups did we promise residents in management responses during this
period?" It identifies recorded promises; it does not establish completion.
Do not include the rejected question about concerns left unanswered in replies.

## Answering and evidence

- Lead with the finding. Use verified counts where useful and a short supported
  interpretation when it helps. Avoid repetition and unnecessary introductions.
- Separate short paragraphs with blank lines. Use bullets and sparse emphasis
  when they improve scanning. Avoid a fixed report template.
- Maximum 1,000 characters, including spaces, for summaries and explanations.
  Requested supporting evidence may expand the whole answer to 3,000 characters;
  the explanation itself stays concise. A citation or headline count alone does
  not qualify for the larger limit. Never cut a qualification or sentence away
  to make an oversized answer appear compliant.
- Show evidence when requested or after the manager accepts an offer. Select by
  relevance, then reliable recency, including contrasting evidence when material.
  No fixed number of excerpts. Use verified references and offer remaining
  relevant information without inventing a remaining count.
- Read community information only. No publishing, contacting residents, tasks,
  source-record changes, or implied actions. The limited preference operation
  writes only the requesting manager's default period.

## Verification and release

Test date boundaries and missing dates, calculated cohorts, preference persistence
and ownership, explicit versus temporary changes, request replay, source links,
answer limits, responsive rendering, and the browser-to-API flow. Automated model
responses are simulated and must be labeled as such. No paid model tests are
authorized by this implementation exercise. Real answer quality remains for the
manager to assess in the configured Mac preview.

Push the completed changes together to the existing Ask Genius draft PR. Do not
merge or deploy production. Supply the compatible Mac source update while
preserving credentials, login, database, and blocked review-analysis settings.
