# Survey corrections — combined PR #12

November 4, 2026. Branch `fix/ask-genius-survey-selection`, stacked on
`feat/lifecycle-email-preview` (#11). The four discussed corrections are now
implemented together. Merge and deployment require separate authorization.

## Behavior and diagnosis

1. Named survey descriptions select that questionnaire's originals. Broad,
   unqualified evaluations cover all types in the chosen period; short
   follow-ups retain their subject. Previously, the preceding type could stick.
2. The model receives rating counts grouped by questionnaire and question,
   alongside all original answers. The shared evidence rules and existing
   survey section now preserve low ratings, mixed feedback, unresolved issues
   and reported safety concerns. Individual aspect ratings are distinct from
   overall experience. Missing saved analysis does not mean missing originals.
   Current source inspection and route tests confirm broad inputs contain the
   original records; the exact requests from the user's Mac were not available.
3. Invitation status distinguishes accepted test sends, simulations, missing
   history, unconfirmed sends, failures and opt-outs in both list and detail.
   Submission status remains separate. Provider acceptance is not proof of
   inbox delivery. The previous detail paragraph always said no email was sent.
4. An untouched blank form no longer starts as saved. A reopened draft or a
   successful save confirms saving; editing clears that confirmation. Existing
   revision guards, failure messages and editable answers are preserved.

The prompt was reread in full with its unchanged output contract. Changes are
integrated into the shared core and survey section, without adding duplicate
examples or hardcoded test answers. Full instructions live at
`services/backend-api/src/services/ask_genius_instructions.txt`.

## Verification

- Ask Genius offline routes/services: 249 passed.
- Survey workflow: 84 passed, four PostgreSQL-specific skips.
- Frontend reviews, Ask Genius and surveys: 155 passed, one existing skip.
- Affected frontend files: ESLint passed; whitespace check passed.
- Full frontend TypeScript check: 87 errors, byte-identical diagnostics on the
  unchanged branch. No added errors; this is not a passing project-wide check.
- Before these changes, the two new rating-input tests failed and 13 scope
  cases passed. The expanded frontend flow suite had eight failures and ten
  passes; after the correction all 18 passed.

The exact 14-question conversation is replayed against nine synthetic
submissions to verify scope and original-answer inputs. Model generation is
mocked. This establishes software behavior, not live-model factual accuracy.
Full captured inputs, outputs, rejected cases, baseline failures and logs are
kept in the user's private test record; no private capture archive is committed.
No live model/email calls, Mac installation, merge or deployment occurred.
Property naming remains a separately queued decision.

## Next action and stopping rule

Update the local preview through a guarded update, then replay the original
14 questions against the user's nine existing responses in all-history scope.
Check nine responses (three maintenance, one per other type), original move-in
answers, low-rated aspects, unresolved maintenance and the reported slip risk,
parking, rent-payment follow-up and renewal uncertainty. Check a date period
excluding the two older submissions. Do not resubmit surveys or resend emails.
Stop at the first factual failure, capture the actual input/output and diagnose
it before changing instructions again. Human acceptance of the new live
answers remains pending; software passes do not substitute for that review.
