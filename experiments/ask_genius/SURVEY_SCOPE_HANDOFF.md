# Survey corrections — combined PR #12

November 4, 2026. Branch `fix/ask-genius-survey-selection`, stacked on
`feat/lifecycle-email-preview` (#11). The four discussed corrections are now
implemented together. The agreed model-input simplification is now added to the
same PR. Merge and deployment require separate authorization.

## Behavior and diagnosis

1. Named survey descriptions select that questionnaire's originals. Broad,
   unqualified evaluations cover all types in the chosen period; short
   follow-ups retain their subject. Previously, the preceding type could stick.
2. The model receives rating counts grouped by questionnaire and question,
   alongside all original answers. The shared evidence rules and existing
   survey section now preserve low ratings, mixed feedback, unresolved issues
   and reported safety concerns. Individual aspect ratings are distinct from
   overall experience. Missing saved analysis does not mean missing originals.
   The user's subsequent private export confirms all nine original records
   reached all four broad requests. Missing source retrieval did not cause those
   omissions. Individual questionnaire answers improved; broad summaries still
   omitted material concerns and made unsupported claims.
3. Invitation status distinguishes accepted test sends, simulations, missing
   history, unconfirmed sends, failures and opt-outs in both list and detail.
   Submission status remains separate. Provider acceptance is not proof of
   inbox delivery. The previous detail paragraph always said no email was sent.
4. An untouched blank form no longer starts as saved. A reopened draft or a
   successful save confirms saving; editing clears that confirmation. Existing
   revision guards, failure messages and editable answers are preserved.

The earlier prompt correction was integrated into the shared core and survey
section. This new step leaves the entire prompt and output contract unchanged.
Full instructions live at
`services/backend-api/src/services/ask_genius_instructions.txt`.

## Model-input simplification

Only the model-facing copy changes. Keep the bound question text once; omit
duplicate context, duplicate free-text labels and form-only constraints. Supply
an identical rating scale once per submission; retain different scales per
question. Preserve all answer values, choices, selected labels, dates, context,
IDs and calculated counts. Source cards and validation use the unchanged full
records. No database, model, provider, prompt, history or review-input changes.

On the four actual captured requests, all nine submissions and 36 answers are
preserved. Total message content is 24.0–24.3% shorter in characters. This is not
a token/cost measurement or evidence of improved answer quality. Duplication
contributing to omissions remains a hypothesis to test.

## Verification and limitations

- Fresh Ask Genius offline suite: 253 passed, including four new preservation
  cases. Model outputs are mocked; these check software behavior, not accuracy.
- Comparison runner: eight offline tests passed for the four-call bound,
  preflight checks and stopping without retries after request/validation errors.
- The first new-test run had two fixture-type errors plus two missing-function
  failures. After correcting the fixtures, baseline was three failed/one passed;
  the implementation then passed all four. All attempts are retained privately.
- Previous combined-update verification, not rerun for this backend-only change:
  84 survey workflow passes/four PostgreSQL skips; 155 frontend passes/one skip;
  affected-file ESLint passed. Project-wide TypeScript had 87 pre-existing errors
  with identical baseline diagnostics. That was not a passing full typecheck.

The user's baseline export records 13 generated requests using gpt-4.1-mini,
128,146 input and 2,237 output tokens; the count question was calculated locally.
Cost was not recorded. Exact private inputs, outputs, failure/rejection reasons
and factual-review notes stay outside this public repository. No new live model
or email call, preview installation, merge or deployment occurred in this step.
Property naming remains separately queued.

## Next action and stopping rule

Run the prepared four-question comparison on the existing Mac preview. It uses
the installed AI adapter, model and validator, with the original frozen chat
history and only simplified survey evidence. No preview update is needed to run
this diagnostic. The earlier outputs are the baseline; no paid baseline rerun.
See `survey_input_comparison/README.md` for scope and complete capture behavior.

Check bad-survey selection, maintenance/near-fall and move-in condition coverage,
parking/rent-payment follow-up, and rent-value uncertainty without invented
delays or causes. Stop on the first request/validation error, then assess facts
separately. Stop at the first factual failure and diagnose the saved input/output
before changing instructions or rerunning. Do not resubmit surveys or send email.
If the diagnostic passes human review, install through a guarded update and
check the normal chat workflow. Human accuracy acceptance remains pending.
