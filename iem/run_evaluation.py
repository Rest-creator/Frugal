#!/usr/bin/env python3
"""IEM's minimal evaluation harness (V1).

Runs a candidate detector against the protected benchmark suite and emits
a Verdict record, per Docs/IGM-IEM-SPEC.md. Refuses to run at all if
integrity_check.py does not pass first (ADR-002, ADR-004: no bare LLM
opinion — verdict traces to concrete harness output, and never runs
against an unverified benchmark store).

Usage: run_evaluation.py <path-to-candidate-detector.py> [candidate_id]
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROTECTED_DIR = ROOT / "benchmarks" / "protected"
VERDICTS_DIR = ROOT / "iem" / "verdicts"


def make_verdict_id(candidate_id: str, evaluated_at: str) -> str:
    # Deterministic from (candidate_id, evaluated_at) so re-running the same
    # evaluation at the same instant doesn't silently mint a second id, but
    # any real change in inputs/time produces a distinct one the deploy
    # actor and human approval can both reference unambiguously.
    h = hashlib.sha256(f"{candidate_id}:{evaluated_at}".encode()).hexdigest()[:12]
    return f"VERDICT-{h}"


def load_benchmark_defs():
    return sorted(p for p in PROTECTED_DIR.glob("*.json") if p.name != "manifest.json")


def run_candidate_against_fixture(candidate_path: Path, fixture_log: Path):
    """Runs the candidate as a subprocess the same way the lab scenario does,
    so this works unmodified against lab/tools/baseline-ssh-detector/detect.py
    and against any future IGM-produced candidate that shares its CLI
    contract (log_path, threshold)."""
    result = subprocess.run(
        [sys.executable, str(candidate_path), str(fixture_log), "5"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout, result.returncode


def evaluate_one(bench_path: Path, candidate_path: Path):
    bench = json.loads(bench_path.read_text())
    fixture_log = PROTECTED_DIR / bench["fixture_log"]

    start = time.time()
    stdout, returncode = run_candidate_against_fixture(candidate_path, fixture_log)
    elapsed_ms = int((time.time() - start) * 1000)

    alerted = "ALERT:" in stdout
    passed = alerted == bench["expected"]["must_alert"]

    return {
        "test_id": bench["id"],
        "pass": passed,
        "metrics": {
            "alerted": alerted,
            "expected_must_alert": bench["expected"]["must_alert"],
            "exec_time_ms": elapsed_ms,
            "detector_returncode": returncode,
        },
        "evidence_ref": stdout.strip(),
    }


def main():
    if len(sys.argv) < 2:
        print("usage: run_evaluation.py <path-to-candidate-detector.py> [candidate_id]")
        sys.exit(1)

    candidate_path = Path(sys.argv[1]).resolve()
    candidate_id = sys.argv[2] if len(sys.argv) > 2 else candidate_path.stem

    integrity = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "integrity_check.py")],
        capture_output=True,
        text=True,
    )
    print(integrity.stdout)
    if integrity.returncode != 0:
        evaluated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        verdict = {
            "verdict_id": make_verdict_id(candidate_id, evaluated_at),
            "candidate_id": candidate_id,
            "benchmark_results": [],
            "adaptive_results": [],
            "regression_results": [],
            "resource_metrics": {},
            "verdict": "rejected",
            "rejection_reason": "protected_benchmark_integrity_check_failed",
            "evidence_refs": [integrity.stdout.strip()],
            "evaluated_at": evaluated_at,
        }
        print(json.dumps(verdict, indent=2))
        write_verdict(verdict)
        sys.exit(1)

    benchmark_results = [
        evaluate_one(bench_path, candidate_path) for bench_path in load_benchmark_defs()
    ]

    all_passed = all(r["pass"] for r in benchmark_results)
    evaluated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    verdict = {
        "verdict_id": make_verdict_id(candidate_id, evaluated_at),
        "candidate_id": candidate_id,
        "candidate_artifact": str(candidate_path),
        "benchmark_results": benchmark_results,
        "adaptive_results": [],
        "regression_results": [],
        "resource_metrics": {
            "total_exec_time_ms": sum(r["metrics"]["exec_time_ms"] for r in benchmark_results)
        },
        "verdict": "approved_for_human_review" if all_passed else "rejected",
        "rejection_reason": None if all_passed else "one_or_more_protected_benchmarks_failed",
        "evidence_refs": [r["evidence_ref"] for r in benchmark_results],
        "evaluated_at": evaluated_at,
    }

    print(json.dumps(verdict, indent=2))
    write_verdict(verdict)
    sys.exit(0 if all_passed else 1)


def write_verdict(verdict: dict):
    VERDICTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = VERDICTS_DIR / f"{verdict['verdict_id']}.json"
    out_path.write_text(json.dumps(verdict, indent=2) + "\n")
    print(f"\nVerdict written: {out_path}")


if __name__ == "__main__":
    main()
