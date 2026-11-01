# Maintenance survey integration

The first survey workflow uses the existing Next.js frontend, FastAPI API,
SQLAlchemy database, authentication and community permissions. It does not create
review feedback, schedule work, send email or queue survey analysis.

| Record | Relationship and purpose |
| --- | --- |
| Community | Existing `organizations.id`; all manager access is scoped to the authenticated community. |
| Resident and unit | Community-scoped external identifiers in `survey_residents` and `survey_units`; fictional inputs only in this simulator. |
| Maintenance occurrence | Unique community/event and community/occurrence identity; ticket, completion timestamp, resident/unit snapshots and optional employee/vendor details. |
| Survey instance | One private token per occurrence; frozen questionnaire, version, rating/choice labels, rendered questions and maintenance context. Draft and final answers remain distinct. |
| Invitation | One durable invitation per instance; prepared recipient/content/link and explicit `simulated` or `suppressed_opt_out` outcome. |
| Submitted answers | Final answers and `submitted_at` on the instance. Ask Genius filters this timestamp, independently of ticket completion. |

The maintenance wording comes unchanged from the earlier BoomSay catalog version
1, template `maintenance_v1`. No saved survey sentiment, topics or analysis exist.
The survey tables are separate from `feedback_items`, so review counts and review
analysis workers continue to operate on reviews.

## Separate fictional Docker Compose preview

Run these commands from this feature checkout, with Docker Desktop running. This
creates the separate Compose project `boomsay-survey-demo`, a dedicated PostgreSQL
volume, and loopback ports 53104/53105. It does not use the installed Mac preview's
database, credentials, analysis, conversations, Compose configuration or ports.
Do not change the project name to match an existing installation.

```bash
docker compose -f experiments/maintenance_surveys/compose.yml up -d --build
docker compose -f experiments/maintenance_surveys/compose.yml logs --tail=40 api
open http://127.0.0.1:53104/surveys
```

The local fictional login is `manager@survey-demo.invalid`, password
`fictional-survey-demo-login`. These public demo credentials and synthetic
encryption/JWT settings are only for this loopback, fictional-data installation.
No real provider key is loaded from the shell or another preview. The initializer
refuses databases containing another community or manager; repeat startup retains
its existing demo community and password. No reset command is part of installation.

The first build installs the existing application's dependencies and can take
several minutes. The demo backend omits the optional large local ML packages, as
repository CI does. No Celery worker or Beat scheduler is needed for surveys.
Redis is available for the existing application; surveys rely on durable database
constraints rather than Redis cooldowns.

## Ingest, inspect and open the invitation

This command passes the readable fictional event through the real ingestion
service. It prepares and persists the invitation and invokes the fake sender at
the provider boundary. It creates no submitted answers.

```bash
docker compose -f experiments/maintenance_surveys/compose.yml exec -T api \
  python -m src.survey_demo simulate survey-demo-fixtures/maintenance-completed.json

docker compose -f experiments/maintenance_surveys/compose.yml exec -T api \
  python -m src.survey_demo inspect fictional-maintenance-event-001

SURVEY_URL="$(docker compose -f experiments/maintenance_surveys/compose.yml exec -T api \
  python -m src.survey_demo link fictional-maintenance-event-001)"
open "$SURVEY_URL"
```

The inspection JSON contains `invitation.status`, its fictional recipient,
subject, text, HTML and actual `survey_url`. A `simulated` result does not mean
provider acceptance, sending or delivery. Repeating the same simulate command
returns the same survey and link without a second invitation, even after restart.

The [event fixture](fixtures/maintenance-completed.json) identifies resident Jamie
Example, unit 204 and ticket DEMO-WO-1001. Its timezone-qualified `completed_at`
records when the ticket was marked completed. Employee/vendor information is
optional and omitted. No vendor PMS schema or connection is used.

For a second occurrence, create a second fictional event on standard input:

```bash
python3 - <<'PY' | docker compose -f experiments/maintenance_surveys/compose.yml exec -T api python -m src.survey_demo simulate -
import json
from pathlib import Path
event = json.loads(Path('experiments/maintenance_surveys/fixtures/maintenance-completed.json').read_text())
event.update(event_id='fictional-maintenance-event-002',
             occurrence_id='fictional-maintenance-occurrence-002', ticket_id='DEMO-WO-1002',
             request_description='the bathroom fan repair')
print(json.dumps(event))
PY
```

This retains the same fictional resident while creating a separate ticket,
occurrence, survey and private link. Replaying an identity with a different ticket
or resident fails instead of redirecting an older link.

## Submit and inspect the original answers

Use the actual private resident form. Select `2 Bad`, `No, still unresolved` and
`Not sure`; optionally enter the comment from the [answer fixture](fixtures/unresolved-answers.json).
The form saves drafts, resumes after reload and shows completion only after the
server persists final answers. The private link requires no manager login.

For a developer route check, this submits the same example through the actual
resident API instead of inserting a response fixture:

```bash
SURVEY_TOKEN="${SURVEY_URL##*/}"
curl --fail-with-body -X POST \
  -H 'Content-Type: application/json' -H 'Origin: http://127.0.0.1:53104' \
  --data-binary @experiments/maintenance_surveys/fixtures/unresolved-answers.json \
  "http://127.0.0.1:53105/api/v1/resident-surveys/$SURVEY_TOKEN/submit"
```

Open `http://127.0.0.1:53104/surveys`, sign in and choose **View answers**. The list
shows both unfinished and completed surveys, the simulated invitation status,
resident, unit, ticket and submission date. Detail shows frozen maintenance
context, original questions, labels and answers. Repeated submits and late draft
writes retain the first completed answer set. A ticket marked completed can still
have an unresolved resident answer; the application preserves both facts.

Restart the application, reopen the private link and dashboard, and confirm the
same stored response remains:

```bash
docker compose -f experiments/maintenance_surveys/compose.yml restart api
docker compose -f experiments/maintenance_surveys/compose.yml exec -T api \
  python -m src.survey_demo inspect fictional-maintenance-event-001
```

Stop the separate preview with `docker compose -f
experiments/maintenance_surveys/compose.yml stop`. Its named volume remains intact.
Do not use `down -v`, database drops, restamping or resets as installation/update
steps.

## Ask Genius and model boundaries

Original finalized survey answers, their question text, choices and labels are
authorized evidence in Ask Genius. Counts come from stored submissions; distinct
resident counts are reported separately. Use a period covering the **submission
date**, not merely the historical ticket completion date. The resident response
timestamp is recorded when the form is actually submitted.

In a separately configured local application, open `/ask-genius` and ask:

- “Show the completed maintenance surveys for this period.”
- “Which submissions say the issue is still unresolved?”
- “What did residents say about their maintenance experience?”
- “Show the original answers behind that.”

Survey evidence opens `/surveys/{public_id}` under manager authentication. Survey
references use source-aware identifiers and do not point to review evidence.
Survey-backed conversations cannot be publicly shared; no survey or resident data
is copied into public snapshots. Existing review-only answers/sharing remain
available under their existing rules.

The supplied isolated Compose demo deliberately has `ASK_GENIUS_ENABLED=false`
and blank provider keys. Use this command **after submitting the resident form**
to inspect the whole Ask Genius flow without a paid model request:

```bash
docker compose -f experiments/maintenance_surveys/compose.yml exec -T api \
  python -m src.survey_demo verify-ask
open http://127.0.0.1:53104/ask-genius
```

Select **[OFFLINE MOCK] Survey verification** in the chat history. The command
passes four questions through the actual authenticated Ask Genius API and saves
the resulting private chat in the demo database. The submission count and
unresolved count are computed from application records. The narrative and its
original-answer follow-up use explicitly labeled `MOCKED MODEL OUTPUT` responses;
their model function is substituted only inside this developer command. The
normal application remains disconnected from AI, so its composer remains
disabled. Existing saved history and evidence can still be inspected.

The command prints `verification_mode: offline_mock`, the conversation ID,
questions, answers, application counts, authorized evidence URLs and their
successful detail-route checks. It also confirms the survey-backed chat cannot
be shared. It refuses foreign databases and requires a real finalized survey.
HTTP/provider boundaries fail closed during verification; no API keys, provider
settings or application environment are changed. Repeating the command creates
another clearly labeled demonstration chat while retaining existing data.

Mocked-model integration tests and this command establish retrieval, answer
handling, original evidence links, counts, authorization and sharing behavior.
They do not establish live AI answer quality. No live-model evaluation is
authorized by this increment; the installed preview's existing AI configuration
is preserved by the separate source updater rather than copied into this demo.

## Provider and deferred work

Survey invitation preparation uses a Resend-compatible provider boundary and the
existing application's transport/configuration. Normal ingestion, API simulation,
demo commands and tests always use the simulated sender, even if a Resend key is
present. Existing simulated invitations cannot turn into real sends after restart.
Resident/community email opt-outs remain honored. No live provider setup is
required for this increment. Real sending would need a separately approved mode,
verified sender domain/configuration and operational handling; no such mode is
enabled here.

Deferred: invitation timing, reminders/quiet hours, automatic survey analysis,
survey topics/sentiment, other survey types, wording changes, visual refinement,
SMS, real PMS connections, public-review solicitation, hosting and deployment.
The future timing remains 24 hours after ticket completion, with one reminder 24
hours after provider acceptance if unanswered, in the property's 9 a.m.–6 p.m.
window. None of those timers or sends is implemented in this increment.

For updating an existing Mac preview without replacing its database or private
configuration, use the separate [preview updater instructions](preview_updates/README.txt).
