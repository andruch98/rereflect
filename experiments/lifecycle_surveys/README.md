# Original lifecycle surveys

This extension uses the seven original questionnaires from
[boomsay-agent/data/survey_catalog.json at 9af23a3811615d08cb4067c293ef81da23b35887](https://github.com/andruch98/boomsay-agent/blob/9af23a3811615d08cb4067c293ef81da23b35887/data/survey_catalog.json).
The recovered catalog is copied unchanged into
`services/backend-api/src/services/data/survey_catalog.json`. Question IDs,
wording, order, required flags, choices, rating labels and comment limits remain
as originally written. Titles/questions bind community and event context when a
new occurrence is created; saved questionnaire snapshots are never rewritten.

| Event selector | Original template | Meaning of the explicit event |
| --- | --- | --- |
| `move_in_completed` | `move_in_v1` | Completed move-in |
| `maintenance_completed` | `maintenance_v1` | Completed maintenance ticket |
| `lease_month_3` | `lease_month_3_v1` | Three-month check-in |
| `lease_month_6` | `lease_month_6_v1` | Six-month check-in |
| `lease_month_9` | `lease_month_9_v1` | Nine-month renewal intent/planning |
| `lease_renewed` | `lease_renewed_v1` | Completed lease renewal |
| `move_out_completed` | `move_out_v1` | Completed move-out |

Each has three required questions and an optional comment. Draft/resume, final
submission, one private link per occurrence, manager list/details, opt-outs and
Ask Genius original-answer evidence use the existing survey workflow. A separate
occurrence creates a separate response even for the same resident. Replaying an
occurrence retains its link and answers. A replay cannot change its survey type.

This does not infer lifecycle dates from resident data or activate timers,
reminders, PMS connections, SMS, automatic analysis or production delivery. An
explicit simulated event selects a questionnaire now. Nine-month renewal intent
is separate from an actual completed renewal. Future date eligibility and
renewal suppression rules still require a source/integration decision.

## Data compatibility

Migration `a3c927b6d801` follows `f2e8463ab154`. It permits null maintenance ticket
and request fields. It retains the existing occurrence table, IDs, foreign keys,
unique occurrence constraints, private tokens, invitations, snapshots, drafts
and submitted answers. The generic ORM name `SurveyOccurrence` retains the
`MaintenanceOccurrence` import alias. No fictitious tickets are attached to
nonmaintenance events. Downgrade refuses if lifecycle records cannot fit the old
required-ticket schema; it never deletes them or invents ticket data.

`POST /api/v1/surveys/simulate` retains its preview/admin and simulation guards.
It accepts all selectors above, `occurred_at` (timezone required), resident/unit
context and `.invalid` email addresses. Legacy `completed_at` input remains
accepted. Maintenance requires `ticket_id` and `request_description`; only
maintenance accepts employee context. Other events reject those fields.
`GET /api/v1/surveys?event_type=move_in_completed` filters the list; omission shows
all types. Returned context identifies `event_type`, `survey_type_label` and
`event_occurred_at`. Old maintenance ticket metadata remains available.

## Prepare all seven in the separate fictional preview

From the repository root, follow the [existing isolated preview setup](../maintenance_surveys/README.md#separate-fictional-docker-compose-preview).
Rebuild from this branch so the API, UI and migration are present. Its ports,
database and public demo login are separate from the installed Mac preview.
No database reset or volume deletion is needed.

```bash
docker compose -f experiments/maintenance_surveys/compose.yml up -d --build
for EVENT_TYPE in move_in_completed maintenance_completed lease_month_3 lease_month_6 lease_month_9 lease_renewed move_out_completed; do
  docker compose -f experiments/maintenance_surveys/compose.yml exec -T api \
    python -m src.survey_lifecycle_demo --community-id 1 --event "$EVENT_TYPE" --test-id lifecycle-review
done
```

The commands print seven private resident links. They prepare fictional pending
surveys and simulated invitations; they do not email or submit answers. Reusing
the same test ID/type reopens its same occurrence. The simulator requires
`BOOMSAY_SURVEY_SIMULATION=true` and the configured preview community. The
existing separate Compose setup supplies both guards. It refuses collisions
with a resident/unit that does not match its fictional identifiers.

Open each printed link, answer and save a draft, reload, then submit. Inspect
`http://127.0.0.1:53104/surveys` using the fictional manager login from the setup.
Filter by type and open the original answers. There should be no maintenance
request heading for nonmaintenance surveys. Complete example inputs and final
answer sets for all seven are in [fixtures.json](fixtures.json); these are
fictional test responses, not proposed changes to questionnaire wording. The
fixture `community_id: 1` is for this isolated demo.

After submitting a selected type, this command saves a private, clearly labeled
Ask Genius demonstration chat with original answers and source links:

```bash
docker compose -f experiments/maintenance_surveys/compose.yml exec -T api \
  python -m src.survey_demo verify-ask --event-type move_in_completed
```

Repeat with any selector above. The default remains maintenance. The command
requires a submitted response for that selected type. Counts use application
records; narrative outputs are labeled mocks. It blocks live model/email HTTP
calls and restores the original configuration. It is a workflow check, not a
judgment of a live model's factual accuracy.

Ask Genius keeps questionnaire types distinct. For example, “How many move-in
surveys?” reads that type only; “Compare move-in and maintenance surveys” reads
both. A topic such as “surveys about maintenance” does not select the maintenance
questionnaire. Type filters survive follow-ups, with a changed type clearing the
prior answer cohort. A request containing “move-in or maintenance surveys” asks
for a clear choice instead of silently dropping a type. Exact issue-resolution
counts apply only to maintenance; mixed-type unresolved counts require a more
specific request. Periods use submission time. Review-only source selection and
survey sharing restrictions remain in place.

## Prepare one guarded email test

Only after this source and migration are installed in the existing port-53004
Mac preview, the existing email-test helper accepts `--event-type`. Omission
still means maintenance. From the source checkout, prepare a move-in test:

```bash
SURVEY_HELPER="$PWD/experiments/maintenance_surveys/email_preview/survey-email-test.py"
cd "$HOME/Downloads/boomsay-dashboard-preview"
python3 "$SURVEY_HELPER" prepare --test-id move-in-review --event-type move_in_completed
```

This prints the invitation and local link without sending. Use the same named
test/type to review it again. A name cannot be reused for a different type. All
existing guards remain: the exact permitted recipient/sender, localhost base,
Lake House preview, opt-outs, completion checks, atomic send reservation,
provider idempotency key, hidden interactive key entry and no redirect. The
helper's separately explicit send action is unchanged; development verification
uses only a fake transport and does not send any email. Nonmaintenance invitation
copy uses the original questionnaire title with a fictional-test disclosure.
The local links do not work for remote prospects.

## Bounded software verification

From `services/backend-api` with repository test dependencies installed:

```bash
python -m pytest --confcutdir=tests/surveys_offline tests/surveys_offline -q
python -m pytest --confcutdir=tests/ask_genius_offline tests/ask_genius_offline -q
python -m pytest --noconftest tests/test_outreach_migration.py -q
```

Set `BOOMSAY_TEST_CAPTURE` to a writable JSONL path for Ask Genius tests to retain
complete mocked inputs, outputs, application answers and validation/rejection
reasons. Test fixture token counts are synthetic; they are not actual model
usage. There are no live model requests, real email sends or provider charges in
these tests. PostgreSQL concurrency tests require the documented separate test
database and skip otherwise. SQLite migration tests check preservation of old
records and links; Docker startup and live PostgreSQL migration are separate
checks. UI integration is verified separately with the frontend changes.
