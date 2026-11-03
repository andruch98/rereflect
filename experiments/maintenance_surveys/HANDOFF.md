# BoomSay survey integration — current handoff

Updated 3 November 2026. This supersedes the earlier handoff's system-font,
separate-page evidence, unsupported-count and unpublished-branch statements.

## Current work

Repository: andruch98/rereflect. Correction branch: fix/survey-genius-continuity.
Base: published survey branch at ccb53d4122a76ffd6045d2bf188d20dfdb712d2d,
which builds on master 59dfd9122b20d0098eceedf8e1d1296e86b6f0a3.
The delivered ZIP's update.json identifies its exact committed source.
Implementation and testing were authorized. Merge and deployment were not.
No Mac installation, real email delivery or paid model request was performed by
this work session. Andres tested the corrections on his Mac: survey counts and
the original-answer popup worked. After the answer-recovery update, he supplied
a successful narrative-answer screenshot and confirmed "Show each answer" passes.
Optional wording polish is deferred.

## Agreed behavior implemented

- Source follows explicit choice or the established chat. Maintenance alone does
  not switch reviews to surveys. Exclusions such as “reviews, not surveys” apply.
  An ambiguous new chat asks “Reviews, surveys, or both?”; a short answer resumes
  its original question and retains the selected period.
- Survey findings retain validated submission/question references, topic links
  and concise topic text for evidence/count follow-ups. They are interpretation
  of original answers, not a claim of saved survey analysis.
- Survey evidence opens an in-chat popup under the relevant topic. The original
  relevant question/answer appears first; “View all answers from this survey”
  expands that same submission. Existing saved sources can load through the
  authenticated survey endpoint. Public snapshots never fetch private surveys.
- The survey-response count starter works without a model call. It counts
  finalized submissions by submission date; drafts/invitations are excluded.
  Two surveys from one resident count as two responses. Unique residents are
  counted only when requested.
- Restored Montserrat, Merriweather and Ubuntu Mono exactly as in master.
  Local preview builds skip Sentry upload/instrumentation; production setup is
  unchanged. Runtime preview telemetry was already disabled.
- Survey-backed chats remain unshareable publicly. Review-only sharing remains.
- Existing-preview ZIP delivery uses port 53004, existing credentials, private
  configuration, database and startup script. A guarded CLI adds one fictional
  maintenance event and simulated invitation; repeating it preserves answers.
  No separate clone, replacement credentials or model mock is required on Mac.

## Answer recovery follow-up — current correction

The failure report named InvalidModelAnswer with the generic invalid_output
reason. Code inspection and replay identified rejection of valid supporting
references on a summary question. The pasted response also showed apparent
invalid JSON line breaks; original provider bytes are unavailable. The fix
replays valid escapes, literal newlines and backslash/newline variants.

Approved and implemented: validate and retain extra references internally while
hiding evidence controls until requested; normalize only unambiguous JSON string
line breaks; preserve raw output; store specific rejection reasons and explain
them plainly; add no automatic model retry. Invalid references and ambiguous or
incomplete output still fail. One shared instruction core plus a short survey
section replaces scattered survey rules, preserving the existing product rules.

Fresh checks: 219 Ask Genius, 35 survey workflow, 122 related interface and 16
updater/packager tests passed; five existing tests skipped. Changed frontend lint
passed. These are mocked/reconstructed software checks, not live AI quality proof.
See verification/answer-recovery/README.md and the downloadable complete record.
The new boomsay-answer-recovery-update ZIP supports the installed 6dd7827360d1a370d59537a0c7407bf5ad5faeff
version as well as previous supported bases. It preserves earlier backups using
a separate backup-before-genius-answer-recovery-update folder. The delivery
manifest identifies the published commit; actual ZIP replay is reported outside
Git after packaging.

## Verification and limits

Current tests use fictional data and mocked/reconstructed model responses. They test software
behavior, validation and data preservation, not a real model's factual judgment.
The continuity report describes the earlier round; the answer-recovery report
describes this round. Both distinguish software checks from human review.
Earlier full-stack reports under verification/full-stack are historical only;
this pass did not reproduce that Docker run.

Earlier continuity verification could not run Docker or Chromium (environment
restrictions). Its frontend build compiled but failed on existing unrelated
TypeScript errors, including invalid Next page exports; the 20 error-bearing
files then matched the survey base. Those build/browser checks were not repeated
for answer recovery. Andres's subsequent Mac walkthrough passed the reported
summary and evidence follow-up. This is limited human verification, not a broad
live-model evaluation. Do not label this release production-ready or fully
browser-tested.

## Combined-test collection correction

GitHub CI for f4c6c222 passed frontend, worker and clean database-migration
checks, but backend pytest stopped before running: both offline suites had a
top-level test_migration module. Separate earlier suite runs did not expose it.
Andres approved renaming the survey test, updating this PR and rerunning CI.

The survey test is now test_survey_migration.py; its contents are byte-for-byte
unchanged. The changed-file inventory uses the new path. The same two migration
files reproduced the import collision before the rename and passed all three
tests together afterward. See verification/test-collection/README.md. GitHub's
complete checks must finish successfully before recommending a merge. This
correction does not change application behavior, schema, prompts or records.

## What remains outside this correction

Real PMS/review-source connections, real survey email delivery, text messaging,
reminders/scheduling, automatic survey analysis, other survey types, survey public
sharing, cloud deployment and live AI quality evaluation remain separate work.
Do not enable them implicitly. Existing review analysis records are preserved;
survey data is stored separately. No new database migration is needed for these
corrections; the underlying survey branch has its original additive migration.

## Working relationship and next action

Andres prefers plain English, brief updates and reviewing one product decision
at a time before implementation. Save agreed decisions without repeating or
contradicting prompt rules. Preserve existing records and the familiar preview
workflow. Ask about unresolved product choices; do not invent them.

Next: review the complete GitHub checks after the test filename correction.
Stop and report any new unrelated blocker before expanding scope. Merging this
correction or the underlying survey branch, and deployment, need explicit
approval. PR #5's e1d7352fa043 migration pin is already superseded by the survey
branch's f2e8463ab154 pin; propose closing #5 as superseded when integrating the
survey branch, rather than replacing the newer pin. Gmail invitation testing
remains a later workflow milestone; do not enable real sending implicitly.
