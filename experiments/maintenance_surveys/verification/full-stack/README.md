# Full-application survey verification

This harness uses the production Next.js build, `src.api.main:app`, actual password
login/JWT authentication, PostgreSQL, Redis and the actual Celery worker. It has
no application route stubs, auth dependency overrides or direct survey fixtures.
Only email delivery (the application's simulated sender) and the model provider
(the OpenAI-compatible HTTP endpoint in model_mock.cjs) are mocked.

The API uses the existing BoomSay preview startup configuration. It runs migrations
and skips unrelated startup seeding through APARTMENT_EXPERIMENT_ORG_ID, as the
existing preview does. The worker runs without Beat. Optional large ML packages
are omitted in these local test images, following the repository CI convention;
no transformer inference or review-analysis execution is claimed.

## Reproduce on a fresh, isolated project

From the complete feature checkout with Docker Desktop, use a separate project
name. Do not point this stack at an installed preview's database or credentials.

```bash
compose=(docker compose -p boomsay-survey-full-20261101 -f experiments/maintenance_surveys/compose.yml -f experiments/maintenance_surveys/verification/full-stack/compose.mock.yml)
"${compose[@]}" build api web worker
"${compose[@]}" up -d --no-build
```

Build before startup so the model mock can reuse the locally built web image's
Node runtime. Ports are loopback-only: web 53204, API 53205, mock observations
53206. The model base URL is model-mock inside this project's network; live keys
are blank. Lowercase and uppercase proxy exclusions cover only internal services.

Install the repository's normal host test tools plus Playwright if needed, then:

```bash
python experiments/maintenance_surveys/verification/full-stack/browser_flow.py work/full-stack/results.json
```

The browser script has no request interception. It logs in through the real UI,
submits the generic event through the authenticated API, fills the public form,
inspects dashboard/originals, asks supported survey questions through the UI,
follows evidence, checks privacy, and restarts only the API. The fixture adds a
fictional pre-existing review with saved analysis, never a completed survey.

A failed run can resume its saved submission with `--resume`; this does not reset
or overwrite it. Use `stop` to stop this project without deleting storage. Do not
use `down -v`. The project name in the script matches the command above.

## Actual run

Final result: complete flow passed on the full application. The report combines
the initial successful event/form/dashboard steps and a resumed Ask Genius check
using the SAME stored submission after fixing the test container's proxy settings.
No database reset, volume deletion or direct completed-survey insert was used.

- Real browser login: HTTP 200, authorized community 1.
- Generic maintenance event: HTTP 200; one pending survey and simulated invitation
  were returned immediately; replay retained the same link.
- Public resident form: draft saved and resumed after reload; final POST 200;
  confirmation followed persistence.
- Dashboard: Jamie Example, unit 204, ticket DEMO-WO-1001, submitted date and
  explicit simulated invitation. Four original question headings and readable
  `2 — Bad`, `No, still unresolved`, `Not sure` and comment were checked.
- Ask Genius: supported list, narrative and original-answer follow-up returned
  HTTP 200 through the application. Application counts were 1 submission and
  1 distinct resident. Two real SDK HTTP calls reached the local model mock,
  each carrying the finalized four questions/options/answers.
- Evidence opened /surveys/04444f50-2379-4832-bcc6-83cb242d9cde and the correct originals.
- Anonymous manager access blocked; survey chat sharing HTTP 422.
- API restart retained answers, submitted_at, original review/saved analysis,
  settings/password and existing chat. No browser page errors.
- PostgreSQL counts: one occurrence, one survey, one invitation, one submitted
  response, one pre-existing review. Worker ready, no tasks received, queue 0.

The narrative answer is explicitly MOCKED MODEL output. This proves integration
and evidence handling, not live AI answer quality or real Resend delivery.

## Blockers resolved during the run

1. The old fictional manager .invalid address failed the existing EmailStr login
   schema. The demo now uses manager@survey-demo.example.com. Authentication was
   not relaxed and no existing account was renamed. Older isolated demos retain
   their storage; use a new project rather than resetting them.
2. The production frontend could not read root-owned public/brand assets as its
   non-root user. Docker COPY now uses the same nextjs ownership as other assets.
3. This environment's internal Docker network did not expose published localhost
   ports. The test overlay uses a separate bridge network with loopback bindings.
4. Inherited lowercase no_proxy overrode uppercase NO_PROXY, so the first narrative
   request received proxy HTTP 403 and surfaced as application HTTP 502. The
   test overlay now defines both internal-only exclusions; the SDK reached the mock.
5. The managed 32 GB VFS Docker store filled during native builds/container copies.
   Only build cache and stateless test containers were reclaimed/recreated; database
   volumes were preserved. Completed images received thin final corrections for
   the demo address and asset ownership. Selected real API/auth/survey/Ask source
   hashes match the checkout, as recorded in provenance.json.

Managed builds used temporary proxy CA secret mounts and the inherited proxy;
TLS validation stayed enabled. No session certificate was committed or baked into
application images. These environment adaptations did not replace app modules.

## Evidence and bounded checks

- results.json: actual browser/API sequence and persisted answers.
- provider-observations.json: two actual SDK requests received by the mock,
  containing fictional finalized original evidence, with no auth headers.
- provenance.json: runtime source hashes, database counts and worker observations.
- dashboard-check.json: actual table fields and all four original headings.
- type-comparison.json: 87 existing diagnostics, no new/removed signatures.
- production-build.log: successful final production build, terminal whitespace normalized.

Additional checks: 42 focused frontend tests, 7 backend demo checks, lint 0 errors
and 42 existing warnings, single migration head f2e8463ab154, Python compilation
and git diff whitespace checks. The full unrelated suites were not rerun.
The system-font change is intact. Survey-count wording remains unchanged.
Mac preview startup, ARM builds, live AI quality and live email remain unverified.
