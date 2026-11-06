# Ask Genius manager questions and answer checks

## Baseline

The approved review baseline is preserved on the rollback branch. The survey work in PRs 12, 11 and 9 was merged to master. It added original survey questions and answers, survey-only examples, conversation sharing and saved inspection of failed attempts. Earlier examples and their recommendations remain in the bank. PR 13, included in the baseline commit 7178e0da, accepts unambiguous grouped survey question references and empty optional selections written as either an empty object or a list. Its regression tests replay the three hosted rent-payment responses numbered 121–123. Those three original hosted failures had valid prose; BoomSay rejected the shape of their references.

This change is a follow-up branch. The OVH user verified HTTPS and 17 submitted surveys. The 100-question study uses fictional records in an isolated database; it does not verify which release OVH is running.

## Changes in this branch

- Accept numeric review IDs and quotation indexes encoded as plain decimal strings, a single in-range star rating, and uniquely matched saved labels and identifiers. After conversion, apply the same restrictions on the community, dates, original question and allowed values.
- Show the resident’s original wording when apostrophes or spacing differ. When the model supplies both a quotation number and text, confirm that they point to the same stored passage. Conflicting references, changed wording, and unknown filters still fail.
- Treat an empty filter as selecting nothing. Record safe field names and error types when a model response fails its format check. Preserve the raw reply for authorized inspection.
- Require coverage of each supplied response for broad survey summaries. Accept multiple distinct findings for one survey and equivalent duplicates with reordered question IDs. For a narrow question, allow verified notes for just the records discussed. Retain checks on missing required coverage, nonexistent questions, and conflicting notes for the same question set.
- Separate a fresh total or “show me all surveys” from “how many of those?” Carry a verified selection only when requested. Provide plain totals, by-type counts, and Yes/No follow-up counts from submitted answers. Count distinct people separately when asked, and distinguish a missing answer from an explicit No.
- Open original sources for “Show the sources” and when the manager accepts an explicit offer to see them. Show a clear message for an empty selection. For direct follow-ups asking for records behind the prior recommendations, use the references saved with that answer.
- Treat “Review the 3-month surveys” as an instruction to examine surveys. Recognize “reviewer,” “9-month planning” and a clear request to list either of two survey types. When asked if a reviewer and a respondent are the same person, disclose that the records contain no verified identity link. A request to interpret a survey comment can reach the model; a request for stored survey sentiment still states the limitation.
- Keep quoted resident language and clear management deadlines separate from record dates. Support an explicit submission day, this month, and a named month with year. Dated filters exclude undated records. Preserve clarification for negated or competing periods. Allow supported written dates in the dashboard before choosing a dropdown period.

The response instructions were aligned with these checks. The complete system message, including the previous survey example bank, is included in the test record. No new permanent rules were added for particular residents or fixtures.

## Additional suggestions from the 100 manager questions

| Priority | Manager problem | Recommendation |
| --- | --- | --- |
| First | A valid source can support a different conclusion from the one the model wrote. In a separate direct validator check, “rent payments” was cited for “rent was too high” and the claim passed. The 9-month survey names conditions for a future decision, not a current assessment. | Before granting live approval, read six live answers against original records: rent payments, conditional renewal, move-out reason, unresolved safety, a mixed review/survey comparison, and a follow-up asking for its sources. Require accurate claims, correct sources, and no unexplained rejection. |
| Next | “Read both sets, but only show complaints in public reviews” reads only reviews in case 91. The displayed complaints are plausible, but the requested cross-check did not take place. | Distinguish records to consult from records to display. Test both sets reach the model and displayed sources obey the manager’s limit. |
| Next | “The 3-month resident” and “the 9-month resident” get the generic question “Reviews, surveys, or both?” Asking what people “posted” can also require clarification in a new chat. | When the milestone clearly refers to a questionnaire, use that survey or ask “Do you mean the 3-month survey?” Preserve genuine ambiguity about the source. |
| Next | Comparing two periods and requesting “only November” while all history is selected return the same generic period message (cases 8, 54, 55). | Ask which year when the month is missing a year. For comparisons, explain that one period can be queried at a time and offer the two specific periods. Keep an explicit narrower period ahead of the general selection. |
| Can wait | Several original questions from a single survey may produce several source cards. Reading them as separate people or responses would be misleading. | If managers report confusion, group question-level evidence under each distinct submission and preserve links for each original question. |

For the live smoke test, keep the full question, original evidence, raw reply, validation decision, independently reviewed factual assessment, and reported token usage and cost. The stored historical hosted replies and offline controlled responses cannot establish a live pass rate.

## Follow-up implementation

The mixed-source workflow consults both authorized sets when explicitly requested and limits the displayed sources to the requested channel. Milestone-resident questions use the corresponding survey, and a fresh question about what someone posted uses reviews. Yearless months ask for the year, two-month comparisons explain the one-period limit, and a selected all-history period can be narrowed by an explicit month and year. Survey evidence dialogs already group question-level references by submission. The instructions now distinguish a payment follow-up from an actual complaint about price. The six-case live check requires a configured provider and is recorded separately from the controlled suite.
