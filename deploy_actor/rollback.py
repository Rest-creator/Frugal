#!/usr/bin/env python3
"""Rollback (V1). Deploy-actor-only operation, logged the same way as a
forward deployment (ARCHITECTURE.md §6).

Usage: rollback.py <deploy_id>
"""
import json
import shutil
import sys
import time
from pathlib import Path

LEDGER_PATH = Path(__file__).resolve().parent / "version_ledger.jsonl"


def find_entry(deploy_id: str):
    if not LEDGER_PATH.exists():
        return None
    for line in LEDGER_PATH.read_text().splitlines():
        entry = json.loads(line)
        if entry["deploy_id"] == deploy_id:
            return entry
    return None


def main():
    if len(sys.argv) < 2:
        print("usage: rollback.py <deploy_id>")
        sys.exit(1)

    deploy_id = sys.argv[1]
    entry = find_entry(deploy_id)
    if entry is None:
        print(f"ROLLBACK BLOCKED: no ledger entry found for {deploy_id}")
        sys.exit(1)

    backup_path = Path(entry["old_artifact_backup"])
    live_target = Path(entry["live_target"])

    if not backup_path.exists():
        print(f"ROLLBACK BLOCKED: backup missing: {backup_path}")
        sys.exit(1)

    shutil.copy2(backup_path, live_target)

    rollback_record = {
        "rollback_of_deploy_id": deploy_id,
        "live_target": str(live_target),
        "restored_from": str(backup_path),
        "rolled_back_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(LEDGER_PATH, "a") as f:
        f.write(json.dumps({"rollback": rollback_record}) + "\n")

    print(f"ROLLED BACK: {live_target} <- {backup_path}")
    print(json.dumps(rollback_record, indent=2))


if __name__ == "__main__":
    main()
