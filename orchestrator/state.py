"""Orchestrator job state (V1).

A JSON file stands in for the Postgres-backed job table described in
ARCHITECTURE.md §6 — this is an explicit, documented V1 simplification
(see README.md's follow-ups), not a silent substitute: the schema below is
exactly the columns a `jobs` table would have, so migrating to Postgres
later is a storage-layer swap, not a redesign.

One job per Finding, moving through:
  new -> igm_running -> igm_done -> iem_running -> iem_done
       -> awaiting_approval -> deployed
  (or -> rejected at the iem_done step if IEM did not approve)
"""
import json
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parent / "state.json"


def load() -> dict:
    if not STATE_PATH.exists():
        return {"jobs": {}}
    return json.loads(STATE_PATH.read_text())


def save(state: dict):
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")


def get_job(state: dict, finding_id: str) -> dict:
    return state["jobs"].setdefault(finding_id, {"finding_id": finding_id, "status": "new"})


def set_job(state: dict, finding_id: str, **fields):
    job = get_job(state, finding_id)
    job.update(fields)
    state["jobs"][finding_id] = job
    return job
