# Survey evidence comparison

This bounded diagnostic changes only the model-facing survey representation.
Original records, review evidence, counts, instructions, history, question,
configured model, provider and generation settings stay fixed. Historical
baseline outputs are compared with one new request for each of four questions;
the baseline is not regenerated. This is a diagnostic, not a statistical claim.

`prepare.py` uses the changed application's `build_messages` against a private
chat export. It refuses any other message/context change. Select exactly four
user-message IDs with `--message-ids`, plus `--export` and a new `--output` path.
Its output contains private information and must never be committed.

The private Mac package contains `run-local.py`, `replay.py`, the prepared
`requests.json`, `checksums.json` and human review criteria `REVIEW.txt`.
Run `python3 run-local.py` with the existing local preview already running.
No installation, migration, database query/write, email, prompt change, model
change, merge or deployment is performed. The four requests use the same
explicit AI connection as Ask Genius and may incur its normal provider charges.

The replay checks the installed prompt and model first, uses the installed
one-call adapter and source validator, and stops on the first request or
validation error. There are no retries or extra judge calls. Human review must
check factual completeness and unsupported claims separately. Stop at the first
factual failure; diagnose the saved request/output before another change or run.

Outputs include readable prior/new answers, full requests/raw responses,
reference/format rejections, recorded token usage, unavailable cost, and pending
human assessments. These are saved locally in a new timestamped ZIP. Existing
conversations are not changed; frozen history avoids confounding this comparison
with new previous answers. A later end-to-end chat check is still required after
any successful diagnostic.
