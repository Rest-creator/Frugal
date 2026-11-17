#!/usr/bin/env python3
"""Deploy actor (V1).

Per Docs/IGM-IEM-SPEC.md: the only component permitted to write live tool
config. Requires BOTH an IEM verdict of approved_for_human_review AND a
matching HumanApproval record (written only by human_approval.py). Refuses
otherwise -- deliberately, so that gap is provable, not assumed.

On success: backs up the current live tool, copies the candidate artifact
into place, and appends a VersionLedger entry with everything needed to
roll back in one action.

Usage: deploy.py <verdict_id>
"""
import json
import shutil
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERDICTS_DIR = ROOT / "iem" / "verdicts"
APPROVALS_DIR = Path(__file__).resolve().parent / "approvals"
BACKUPS_DIR = Path(__file__).resolve().parent / "backups"
LEDGER_PATH = Path(__file__).resolve().parent / "version_ledger.jsonl"


def load_json(path: Path):
    return json.loads(path.read_text())


def append_ledger(entry: dict):
    with open(LEDGER_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def deploy(verdict_id: str):
    verdict_path = VERDICTS_DIR / f"{verdict_id}.json"
    approval_path = APPROVALS_DIR / f"{verdict_id}.json"

    if not verdict_path.exists():
        print(f"DEPLOY BLOCKED: no verdict found for {verdict_id}")
        return False

    verdict = load_json(verdict_path)

    if verdict.get("verdict") != "approved_for_human_review":
        print(f"DEPLOY BLOCKED: verdict {verdict_id} is '{verdict.get('verdict')}', not approved.")
        return False

    if not approval_path.exists():
        print(f"DEPLOY BLOCKED: no human approval on file for {verdict_id} (expected {approval_path}).")
        return False

    approval = load_json(approval_path)
    if approval.get("verdict_id") != verdict_id:
        print("DEPLOY BLOCKED: approval record does not reference this verdict_id.")
        return False

    candidate_artifact = Path(verdict["candidate_artifact"])
    if not candidate_artifact.exists():
        print(f"DEPLOY BLOCKED: candidate artifact missing: {candidate_artifact}")
        return False

    # Resolve the live target from the candidate's own metadata, written by
    # IGM, so deploy.py never hardcodes per-candidate target paths.
    candidate_json_path = candidate_artifact.parent / "candidate.json"
    candidate_meta = load_json(candidate_json_path)
    reference_tool = ROOT / candidate_meta["target_tool"]

    # Per ADR-008: deploy.py never writes to the pristine, git-tracked
    # reference artifact (reference_tool) -- it mutates a sibling live.py
    # instead, gitignored, seeded from the reference on first deploy. A
    # prior version of this script overwrote the reference tool directly,
    # and that mutated state got committed to git as if it were the
    # pristine starting artifact, corrupting the demo for a fresh clone.
    live_target = reference_tool.with_name("live.py")
    if not live_target.exists():
        shutil.copy2(reference_tool, live_target)

    deploy_id = f"DEPLOY-{uuid.uuid4().hex[:12]}"
    deployed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUPS_DIR / f"{deploy_id}-{live_target.name}.bak"
    shutil.copy2(live_target, backup_path)

    shutil.copy2(candidate_artifact, live_target)

    ledger_entry = {
        "deploy_id": deploy_id,
        "verdict_id": verdict_id,
        "candidate_id": verdict["candidate_id"],
        "approved_by": approval["approved_by"],
        "approval_notes": approval.get("notes", ""),
        "live_target": str(live_target),
        "old_artifact_backup": str(backup_path),
        "new_artifact_source": str(candidate_artifact),
        "deployed_at": deployed_at,
        "rollback_command": f"python3 deploy_actor/rollback.py {deploy_id}",
    }
    append_ledger(ledger_entry)

    print(f"DEPLOYED: {live_target} <- {candidate_artifact}")
    print(f"Backup of previous version: {backup_path}")
    print(f"Ledger entry: {deploy_id} (rollback: {ledger_entry['rollback_command']})")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: deploy.py <verdict_id>")
        sys.exit(1)

    ok = deploy(sys.argv[1])
    sys.exit(0 if ok else 1)
