"""Durable, fail-closed six-request budget at the provider boundary.

Keep the manifest and ledger outside Git on a private persistent volume. A
reservation survives process crashes and is never automatically attempted again.
"""
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class ExperimentBlocked(RuntimeError):
    pass


def active():
    return bool(os.environ.get("APARTMENT_EXPERIMENT_ORG_ID"))


@contextmanager
def connection():
    path = os.environ.get("APARTMENT_EXPERIMENT_LEDGER")
    if not path or not Path(path).is_absolute():
        raise ExperimentBlocked("Set an absolute private APARTMENT_EXPERIMENT_LEDGER path")
    Path(path).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(fd)
    os.chmod(path, 0o600)
    db = sqlite3.connect(path, timeout=30)
    try:
        db.execute("CREATE TABLE IF NOT EXISTS attempts (source_id TEXT PRIMARY KEY, request TEXT NOT NULL, attempted_at TEXT NOT NULL, response TEXT, error TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS control (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.commit()
        yield db
    finally:
        db.close()


def reserve(source_id, request):
    manifest_path = os.environ.get("APARTMENT_EXPERIMENT_MANIFEST")
    if not manifest_path:
        raise ExperimentBlocked("Private six-record manifest is required")
    records = json.loads(Path(manifest_path).read_text())["records"]
    if len(records) != 6 or len({r["source_id"] for r in records}) != 6:
        raise ExperimentBlocked("Manifest must contain exactly six unique IDs")
    record = next((r for r in records if r["source_id"] == source_id), None)
    if record is None:
        raise ExperimentBlocked("Source ID is outside the approved six records")
    actual = json.loads(request["messages"][-1]["content"])
    if actual != {"text": record["text"], "star_rating": record["star_rating"]}:
        raise ExperimentBlocked("Model input differs from private manifest")
    digest = hashlib.sha256(json.dumps(records, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute("SELECT value FROM control WHERE key='manifest'").fetchone()
        if previous and previous[0] != digest:
            raise ExperimentBlocked("Do not reuse an experiment ledger with changed inputs")
        db.execute("INSERT OR IGNORE INTO control VALUES ('manifest', ?)", (digest,))
        stopped = db.execute("SELECT value FROM control WHERE key='stopped'").fetchone()
        if stopped:
            raise ExperimentBlocked("Experiment stopped after shared configuration error: " + stopped[0])
        if db.execute("SELECT 1 FROM attempts WHERE source_id=?", (source_id,)).fetchone():
            raise ExperimentBlocked("This review has already been attempted; explicit rerun authorization required")
        if db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] >= 6:
            raise ExperimentBlocked("Six-request limit reached")
        db.execute("INSERT INTO attempts(source_id, request, attempted_at) VALUES (?, ?, ?)",
                   (source_id, json.dumps(request, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))
        db.commit()  # Durable BEFORE crossing the provider boundary.


def finish(source_id, *, response=None, error=None, stop=False):
    with connection() as db:
        db.execute("UPDATE attempts SET response=?, error=? WHERE source_id=?",
                   (json.dumps(response, ensure_ascii=False) if response is not None else None, error, source_id))
        if stop:
            db.execute("INSERT OR REPLACE INTO control VALUES ('stopped', ?)", (error or "provider failure",))
        db.commit()
