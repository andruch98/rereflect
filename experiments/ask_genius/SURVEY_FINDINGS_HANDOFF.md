# Survey summary coverage — November 5, 2026

Approved scope: source-linked factual findings for every supplied survey before broad
summaries, in the same model request. Findings are not resident answers, saved sentiment,
manager-visible prose, or subsequent chat history. The current original answers and the
complete eight-example bank are preserved. Reviews and individual-answer requests retain
the existing format. No new classifier, provider, model, retry or extra model call.

The app recognizes broad assessment/improvement phrases after existing source/type/period
resolution, sets survey_findings_required, and checks exactly one finding per supplied
survey with valid answered-question references. These checks verify coverage and reference
existence only: a model can still omit a concern inside a finding or misstate its meaning.
Human comparison with originals is required. Unknown, duplicate or missing surveys/questions
are rejected without retry. The known displayed-label reference rejection remains deferred.

Output capacity is 1200 + 160 tokens per supplied survey for these requests (max 100 surveys);
ordinary requests retain 1200. The four-survey check allows 1840 per call. This reserves room
for factual notes; it is not guaranteed usage. Manager prose limits are unchanged.

The portable round2 builder now accepts --summary-check. It runs only five questions against
the SAME four round2 submissions: attention list, improvements, overall assessment, then
fresh attention and overall checks. First three form a new chat; earlier original turns are
not replayed. At most five paid calls, zero retries. All failures, model requests, raw notes
and outputs are exported. App/DB installation and browser Share are not exercised.

Stop after five questions. Both attention lists and the improvement/overall summaries must
preserve the second-fob issue, rude-but-resolved maintenance, and community-conditions move-out;
no invented specific noise/parking cause or rent-value judgment. A software failure is not
an accuracy pass. Earlier results are a historical comparison, not a controlled paired run.

Software validation: 317 offline checks passed. The initial broad run had 316 passing and
one older synthetic response fixture missing the new required findings; that fixture was
updated and all 317 passed. These use synthetic responses, not live factual evaluation.
Full request/output captures and both run logs are retained in the verification artifact.
Final package commit/tree provenance is recorded in its source.json.
No live model calls, emails, merge or deployment are authorized for this implementation step.
