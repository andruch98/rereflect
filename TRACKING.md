# Rereflect — Development Tracking Notes

---

## Product Usage Enrichment — follow-ups

> Added: 2026-06-28 (aspect 3 fix wave 1)

### (a) PRE-EXISTING: churn_calibration.py beat tasks appear undecorated/unregistered — FIXED on `feat/per-org-churn-model` (2026-08-14)

`services/worker-service/src/tasks/churn_calibration.py` defines `refit_all_orgs`,
`refit_global_calibration`, and `purge_old_calibration_models` as plain Python
functions without `@shared_task` decorators.  The beat schedule in `celery_app.py`
dispatches all three by dotted name — they will raise `celery.exceptions.NotRegistered`
at runtime and silently never execute.

Action: audit all beat-scheduled tasks against a live worker startup log
(`celery inspect registered`), add `@shared_task(name="<dotted.name>")` to any
undecorated function, and add a registration assertion test for each.
This is a pre-existing issue unrelated to the product-usage-enrichment feature;
handle in a dedicated fix pass to avoid scope creep.

**Close-out (2026-08-14):** the dedicated fix pass landed as aspect 1 of
`feat/per-org-churn-model` (`calibration-beat-fix`). The three functions are now
`@shared_task(name="src.tasks.churn_calibration.<name>")` — registration-only, no body
change — and the sweep also caught `classifier_training.retrain_all_orgs` (same defect
class, M5.2 weekly refit) plus the `churn_playbooks.purge_old_executions` task-name
mismatch (its `@shared_task name=` lacked the `src.` prefix; the earlier fix had only
repaired the beat side). `test_beat_schedule_integrity.py` now asserts real Celery
registration and name-consistency for every beat entry, and the stale
`usage_metrics.py` NOTE ("address in a separate audit pass") is deleted.

### (b) usage_score_service.py is duplicated across backend-api and worker-service

`services/backend-api/src/services/usage_score_service.py` and
`services/worker-service/src/services/usage_score_service.py` are byte-identical.
Both files now carry a `# DUPLICATED` header comment as a reminder.

If the scoring logic diverges in future, migrate to a shared internal package
(e.g. `packages/usage-score/`) consumed by both services, or expose it via a
lightweight RPC call so there is a single source of truth.

### (b2) segment_service.py is duplicated across backend-api and worker-service

`services/backend-api/src/services/segment_service.py` and
`services/worker-service/src/services/segment_service.py` are byte-identical
(same reasoning as (b) — the pure `classify_segment` classifier is needed by the
backend on ingest and by the worker's nightly `recompute_segments` task). Both
carry a `# DUPLICATED` header. Keep them in sync; same shared-package migration
path as (b) applies. Note the worker also mirrors the `segment` column on its
`CustomerHealth` model (`src/models/__init__.py`, "catch-up" convention).

### (c) CLOSED — recompute_usage_scores is keyset-paged (#41, 2026-10-21)

`recompute_usage_scores()` no longer calls `db.query(CustomerUsage).all()`. It iterates the table
in keyset-paged batches of 1,000 (`_iter_customer_usage_rows`), resolving trend baselines once
per page, while preserving the per-row score/trend/health recompute and the
once-per-customer-per-day history snapshot. Shipped in #52.

---

## Product Usage Enrichment — final-review follow-ups

> Added: 2026-06-29 (final-review fix wave)

### (d) I-list-column: last_active_at (product usage) now surfaced on customer list — DONE

`CustomerListItem` previously lacked a `last_active_at` field; the frontend column
always displayed "—".  Fixed: `last_active_at: Optional[datetime] = None` added to
`CustomerListItem`; `list_customers` fetches `customer_usage` rollup rows for the
current page's emails in a single bulk query (keyed by email dict — no N+1) and
populates the field per-item; org-scoped; customers without a rollup row → `None`.
Covered by 4 new TDD tests in `tests/test_customers.py::TestCustomerListLastActiveAt`.

### (e) CLOSED — raw usage_events retention purge shipped (#40, 2026-10-21)

`purge_old_usage_events` deletes `usage_events` older than `USAGE_EVENT_RETENTION_DAYS`
(default 90, env-configurable) and is registered on the weekly beat schedule
(`purge-old-usage-events`). Rows with a NULL `occurred_at` are kept. Idempotent; covered by the
usage-metrics and beat-integrity suites. Shipped in #52.

### (f) DEFERRED (blocked) — process_usage_event still re-aggregates all events per invocation (#42)

`_do_process_usage_event` (worker-service) recomputes the entire rollup by scanning
all historical events for a customer each time a single new event arrives.  At scale
this is O(events_total) work per new event.

**Deferred deliberately (PR #52):** `customer_usage` has no processed-event marker, so a Celery
replay of the same `external_event_id` is indistinguishable from a first sighting
(`events_total += 1` would double-count), and the 7/14/30-day counters cannot be decremented
when events age out. Exact parity needs a schema marker or a per-day bucket table. Revisit when
per-customer event counts exceed ~10 k.

### (g) CLOSED — rollup datetimes are normalised to naive UTC (#43, 2026-10-21)

`_compute_rollup_from_events` runs `now` and every `occurred_at` through `_to_naive_utc`, so a
tz-aware value is converted (not compared raw) and cannot raise
`TypeError: can't compare offset-naive and offset-aware datetimes`. Naive results are unchanged.
Shipped in #52.

### (h) CLOSED — /usage time series is now zero-filled (#44, 2026-10-21)

`GET /api/v1/customers/{email}/usage` now returns exactly `days` daily buckets (30/60/90),
oldest → today (UTC), with `event_count: 0` on inactive days. The window starts at midnight of
the oldest bucket instead of `now - days`, so chart consumers get a continuous baseline.
Covered by `test_customers_usage.py::test_time_series_is_zero_filled_to_window` and
`test_time_series_window_ends_today`.

ORIGINAL ENTRY: `GET /api/v1/customers/{email}/usage` returned only days with at least one
event, so frontend charts could render discontinuous series or misalign the x-axis.
