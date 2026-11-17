#!/usr/bin/env python3
"""Human approval gate (V1).

Per ARCHITECTURE.md §6/§3 and Docs/DECISIONS_LOG.md ADR-005: no candidate
reaches production without a human-authored HumanApproval record. This
script is the ONLY way such a record gets created — it is never called by
IGM, IEM, or deploy.py itself, and it refuses to approve a verdict that
IEM did not itself mark approved_for_human_review (a human can say no to
an approved verdict, but cannot use this tool to wave through a rejected
one).

Usage: human_approval.py <verdict_id> <approved_by> [notes]
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERDICTS_DIR = ROOT / "iem" / "verdicts"
APPROVALS_DIR = Path(__file__).resolve().parent / "approvals"


def main():
    if len(sys.argv) < 3:
        print("usage: human_approval.py <verdict_id> <approved_by> [notes]")
        sys.exit(1)

    verdict_id = sys.argv[1]
    approved_by = sys.argv[2]
    notes = sys.argv[3] if len(sys.argv) > 3 else ""

    verdict_path = VERDICTS_DIR / f"{verdict_id}.json"
    if not verdict_path.exists():
        print(f"REFUSED: no such verdict: {verdict_path}")
        sys.exit(1)

    verdict = json.loads(verdict_path.read_text())

    if verdict.get("verdict") != "approved_for_human_review":
        print(
            f"REFUSED: verdict {verdict_id} is '{verdict.get('verdict')}', "
            f"not 'approved_for_human_review' — IEM did not clear this candidate; "
            f"this tool will not override that."
        )
        sys.exit(1)

    APPROVALS_DIR.mkdir(parents=True, exist_ok=True)
    approval = {
        "verdict_id": verdict_id,
        "candidate_id": verdict["candidate_id"],
        "approved_by": approved_by,
        "approved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "notes": notes,
    }
    out_path = APPROVALS_DIR / f"{verdict_id}.json"
    out_path.write_text(json.dumps(approval, indent=2) + "\n")

    print(f"Approval recorded: {out_path}")
    print(json.dumps(approval, indent=2))


if __name__ == "__main__":
    main()
