# Current handoff — 27 October 2026

Product: Ask Genius for the Lake House preview, answering from saved reviews and
saved analysis. It does not re-run analysis. Surveys and management responses
remain future sources; source mutations, publishing, tasks, and portfolio
comparisons are outside this MVP.

Branch: feat/boomsay-ask-genius. Existing draft PR:
https://github.com/andruch98/rereflect/pull/3, stacked on the review inbox branch.
The user authorized pushing the completed improvements together. No merge or
production deployment is authorized.

Current increment: consolidated instructions, concise readable answers, verified
supporting evidence, the four approved starters and a grouped question library,
required period selection, and an explicitly saved account default. A temporary
period change must not alter that default. Missing posting dates are disclosed,
not replaced with import dates. See APPROVED_MVP.md for approved behavior and
IMPLEMENTATION.md for implementation and verification details.

The source-only Mac updater retains the existing model/key, login, saved data,
database and blocked review-analysis settings. It pins an exact source commit.
Startup applies the new nullable user-preference migration. After that migration,
restoring old source alone is not a supported rollback; preserve the source
backup and follow the package recovery guidance.

Automated model responses are simulated. No real provider calls were made for
this increment. UI tests and localhost HTTP checks passed; current visual
browser validation was unavailable. Actual answer quality and Mac runtime
validation remain for the configured preview. Do not present synthetic answers
or previous layout screenshots as current live validation.
