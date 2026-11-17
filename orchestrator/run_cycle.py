#!/usr/bin/env python3
"""Orchestrator — single-pass job-loop driver (V1).

Drives the Finding -> IGM -> IEM -> (human approval, out of band) -> Deploy
cycle described in ARCHITECTURE.md by shelling out to each actor's own
script, exactly the way a human operator ran them by hand in the prior two
sessions. The orchestrator adds nothing those scripts didn't already
enforce — it does not call deploy.py until an approval file already exists
on disk, and it never writes one itself. That decision stays entirely with
a human, every cycle, for every verdict.

Run with --once for a single pass (used by CI/tests and by `loop.py`), or
import run_cycle() directly.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import state as state_mod  # noqa: E402

CANDIDATES_DIR = ROOT / "candidates"
APPROVALS_DIR = ROOT / "deploy_actor" / "approvals"


def discover_findings():
    """Finding records are markdown files named FINDING-*.md directly under
    candidates/ (not inside a CAND-*/ subdirectory, which holds generated
    candidates instead)."""
    return sorted(p.stem for p in CANDIDATES_DIR.glob("FINDING-*.md"))


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def advance_job(job: dict) -> dict:
    finding_id = job["finding_id"]
    status = job["status"]

    if status == "new":
        print(f"[{finding_id}] new -> running IGM")
        result = run([sys.executable, str(ROOT / "igm" / "generate_candidate.py"), finding_id])
        if result.returncode != 0:
            print(result.stdout, result.stderr)
            job["status"] = "igm_failed"
            job["error"] = (result.stdout + result.stderr).strip()
            return job
        # Parse the candidate id out of IGM's own JSON block (everything
        # after its first "Wrote candidate: ..." line) instead of guessing
        # its naming convention.
        candidate_json = json.loads("\n".join(result.stdout.splitlines()[1:]))
        job["candidate_id"] = candidate_json["id"]
        job["status"] = "igm_done"
        return job

    if status == "igm_done":
        candidate_path = CANDIDATES_DIR / job["candidate_id"] / "detect.py"
        print(f"[{finding_id}] igm_done -> running IEM against {candidate_path}")
        result = run([sys.executable, str(ROOT / "iem" / "run_evaluation.py"),
                      str(candidate_path), job["candidate_id"]])
        # run_evaluation.py prints the verdict JSON block then a trailing
        # "Verdict written: <path>" line; parse the verdict back out of
        # that file rather than re-parsing stdout.
        verdict_line = [l for l in result.stdout.splitlines() if l.startswith("Verdict written:")]
        if not verdict_line:
            job["status"] = "iem_failed"
            job["error"] = (result.stdout + result.stderr).strip()
            return job
        verdict_path = Path(verdict_line[0].split("Verdict written:")[1].strip())
        verdict = json.loads(verdict_path.read_text())
        job["verdict_id"] = verdict["verdict_id"]
        job["verdict"] = verdict["verdict"]
        job["status"] = "awaiting_approval" if verdict["verdict"] == "approved_for_human_review" else "rejected"
        return job

    if status == "awaiting_approval":
        approval_path = APPROVALS_DIR / f"{job['verdict_id']}.json"
        if not approval_path.exists():
            print(f"[{finding_id}] awaiting_approval -> no approval on file yet, holding")
            return job
        print(f"[{finding_id}] awaiting_approval -> approval found, deploying")
        result = run([sys.executable, str(ROOT / "deploy_actor" / "deploy.py"), job["verdict_id"]])
        print(result.stdout)
        if result.returncode != 0:
            job["status"] = "deploy_blocked"
            job["error"] = (result.stdout + result.stderr).strip()
            return job
        deploy_line = [l for l in result.stdout.splitlines() if l.startswith("Ledger entry:")]
        job["deploy_id"] = deploy_line[0].split(":")[1].strip().split(" ")[0] if deploy_line else None
        job["status"] = "deployed"
        return job

    # Terminal states: deployed, rejected, igm_failed, iem_failed, deploy_blocked
    return job


def run_cycle():
    state = state_mod.load()

    for finding_id in discover_findings():
        state_mod.get_job(state, finding_id)

    changed = False
    for finding_id, job in list(state["jobs"].items()):
        before = dict(job)
        after = advance_job(job)
        state["jobs"][finding_id] = after
        if after != before:
            changed = True

    if changed:
        state_mod.save(state)

    return state


if __name__ == "__main__":
    final_state = run_cycle()
    print(json.dumps(final_state, indent=2))
