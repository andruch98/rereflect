# BoomSay on a small Linux VPS

This separate Compose project keeps the current BoomSay frontend, FastAPI API,
Celery worker, PostgreSQL and Redis together. Caddy adds same-origin HTTPS.
It does not deploy the marketing site or copy/change the installed Mac database.
The source includes the seven original lifecycle questionnaires from PR #9.

**Prepared configuration is not a tested deployment.** A fresh host build,
start, TLS/login/user-flow tests, resource measurements and backup restore must
all succeed before reporting the VPS ready. Static limits do not prove RAM fit.

## Host contract and access

- Checkout: `/opt/boomsay/current` (a pinned, reviewed release checkout).
- Compose: `deploy/ovh/compose.yml`, project `boomsay-cloud`.
- Private environment: `/etc/boomsay/boomsay.env`, owner root, mode `0600`.
- PostgreSQL service/user/database: `postgres` / `boomsay` / `boomsay`.
- Named volumes: `postgres_data`, `redis_data`, `worker_state`, `caddy_data`,
  `caddy_config` within this project's namespace.
- Docker and Compose are required on the Linux host. The launcher pins the
  local Docker socket; it does not use a saved remote Docker context. Use the
  project wrapper `sudo python3 deploy/ovh/compose.py ...` for maintenance and
  backups too: it removes inherited overrides only for interpolated app values,
  so the private env file controls their effective values. Proxy, Docker auth
  configuration and unrelated SDK environment are preserved.
- Use a dedicated app hostname whose DNS points to the VPS. Existing main-site
  nameservers, website and email records must be retained.
- Only Caddy publishes host ports80/443. Database, cache, API and frontend stay
  inside Docker networks. SSH access, host firewall and backups are prepared
  separately under `host/`.
- The existing manager JWT authentication protects community data. Public
  account registration is blocked at Caddy for this operator-provisioned demo.
  Private resident links continue to work. No proxy Basic Auth is layered onto
  API requests because it would collide with their Bearer Authorization header.

## First deployment

Provision the private environment from `boomsay.env.example` using independently
generated secrets. Do not commit it or put passwords/API keys in chat. The
validator displays field names only and refuses weak sample secrets, reused
secrets, malformed values, an exposed environment file and main marketing hosts.

From the checkout on the prepared VPS:

```bash
sudo bash deploy/ovh/launch.sh check
sudo bash deploy/ovh/launch.sh build
sudo bash deploy/ovh/launch.sh start
sudo bash deploy/ovh/launch.sh prepare-surveys
```

Builds run sequentially. The launcher's start step first waits for PostgreSQL
and Redis, then runs a one-shot Alembic migration. It fails before rolling out
the API/worker if that gate fails. The API's ordinary startup migrations remain
enabled in all other installs; this Compose project explicitly declares that
the external gate owns migrations. Then the guarded initializer creates one
fictional community/manager in an empty database. It refuses a database that
does not match the fictional demo and never resets existing records/passwords.

The manager email is `manager@survey-demo.example.com`; its password is the
private `SURVEY_DEMO_PASSWORD`, not the published local-preview password. The
runtime backend does not receive this password after initialization.

Seven pending fictional surveys are prepared using a stable `cloud-demo`
identifier. Repeat preparation preserves links, drafts and submissions. Their
private URLs are stored in `/var/lib/boomsay/resident-links.txt`, mode0600.
No answers are submitted and no invitation is sent.

Narrative AI is off until an approved provider/model/key is configured in the
private environment and the backend recreated. Database counts and original
answers can be checked without a model. Actual provider requests, token usage
and cost must be captured separately when testing real model output. Both
backend and worker have blank mail-provider keys; real delivery remains a
separate action. The application provider code and worker task registry remain
present. Optional transformer/embedding dependencies remain in the images;
model weights are not prebaked or activated for this initial demo.

## Capacity profile and gates

| Component | Runtime memory ceiling |
| --- | ---: |
| PostgreSQL |384MiB |
| Redis |192MiB |
| API (one process) |768MiB |
| Celery (one child, prefetch1, full task registry and Beat) |1024MiB |
| Next.js |512MiB |
| Caddy |128MiB |
| Total component ceilings |3008MiB |

These are a starting configuration, **not measured usage or a guarantee**.
The host needs memory for Linux, Docker, filesystem cache, builds and backups.
Models/training or more simultaneous work can exceed this profile. Redis uses
AOF persistence (`appendfsync everysec`) and `noeviction`: queue data is not
silently discarded when the memory budget is reached. The worker keeps all
normal tasks and its scheduler; concurrency1 reduces simultaneous processing.
Beat state has a persistent volume with the image's non-root user ownership.

Do not run several builds alongside a busy demo. Build images sequentially;
if the target cannot build within its memory budget, build the same images on
a larger builder and transfer them. Do not substitute swap for proving4GB fit.

On the real4GB VPS, record separate five-minute windows, once idle and once
while actual login, dashboard navigation, all seven survey submissions and
Ask Genius questions/background analysis are exercised:

```bash
sudo python3 deploy/ovh/measure-fit.py --phase idle --seconds 300 --output /var/lib/boomsay/verification/idle
sudo python3 deploy/ovh/measure-fit.py --phase active --seconds 300 --output /var/lib/boomsay/verification/active
```

The directories must be new, so a later run cannot overwrite prior evidence.
The script records host available memory/swap, each real container's sampled
usage, cgroup peak/events, health, restarts and OOM observations. It keeps secret
values and resident/model content out of resource logs. It fails its resource
window if the host is not approximately4GB, headroom falls below768MiB, total
swap use reaches64MiB, swap grows excessively, health fails, any container restarts/OOMs, or peak evidence
is unavailable. The `active` label does not generate or prove a workload:
retain the executed workflow record alongside these observations.

Full deployment acceptance also requires successful TLS and manager login,
all questionnaire types/draft/resume/submission/originals, cross-type Ask Genius
counts/evidence/follow-ups, actual queue work, restart persistence, external port
checks and a restored backup in a separate database. Distinguish mocked AI,
software checks and human judgment. A missing provider key blocks the live-model
part; it must not be called a passed live-model test.

## Operations

`launch.sh status` shows this project's status. `launch.sh stop` stops only
this project and retains volumes. There is no reset/delete-volumes command.
Take the host backup before each upgrade, pin the next source release, build
sequentially and run the explicit gate before application rollout. Do not run
two releases' workers against the same queue or schema. A failed migration can
require a reviewed forward fix or restore; never automatically downgrade a
database that contains lifecycle records.

Logs rotate at10MiB with three files per long-running service. API access logs
are off and Caddy access logging is not enabled because survey URL paths carry
private tokens. Private build/startup errors should be retained on the server.

## References verified while preparing this configuration

- Docker Compose services, memory limits, health/dependency conditions and
  internal networks: https://docs.docker.com/reference/compose-file/services/
- Caddy handle routing preserves `/api` paths (unlike `handle_path`):
  https://caddyserver.com/docs/caddyfile/directives/handle
- Caddy Basic Auth uses the Authorization header (reason it is not layered over
  JWT requests here): https://caddyserver.com/docs/caddyfile/directives/basic_auth
- Direct retrieval of Caddy reverse_proxy/automatic-HTTPS reference pages timed
  out in this session. Caddy config validation and actual TLS remain host gates.
