#!/usr/bin/env python3
"""IEM's protected-benchmark integrity gate.

Per ARCHITECTURE.md §4 / Docs/DECISIONS_LOG.md ADR-002: IEM must verify the
protected benchmark store against its known-good manifest before every
evaluation run, and fail CLOSED (refuse to evaluate) on any mismatch —
including a missing manifest, a missing file, an extra untracked file, or a
changed hash. This is the control that stops the subject under test (or
anything else) from silently weakening the standard it's judged against.

Exit code 0 = integrity verified, safe to proceed to evaluation.
Exit code 1 = integrity check failed; caller MUST NOT run an evaluation.
"""
import hashlib
import json
import sys
from pathlib import Path

PROTECTED_DIR = Path(__file__).resolve().parent.parent / "benchmarks" / "protected"
MANIFEST_PATH = PROTECTED_DIR / "manifest.json"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def check() -> tuple[bool, list[str]]:
    problems = []

    if not MANIFEST_PATH.exists():
        return False, [f"manifest missing: {MANIFEST_PATH}"]

    try:
        manifest = json.loads(MANIFEST_PATH.read_text())
    except json.JSONDecodeError as e:
        return False, [f"manifest unparseable: {e}"]

    expected_files = manifest.get("files", {})

    actual_files = {
        p.relative_to(PROTECTED_DIR).as_posix()
        for p in PROTECTED_DIR.rglob("*")
        if p.is_file() and p.name != "manifest.json"
    }

    expected_set = set(expected_files.keys())

    for extra in sorted(actual_files - expected_set):
        problems.append(f"untracked file present (not in manifest): {extra}")

    for missing in sorted(expected_set - actual_files):
        problems.append(f"sealed file missing from disk: {missing}")

    for rel, expected_hash in expected_files.items():
        path = PROTECTED_DIR / rel
        if not path.exists():
            continue  # already reported above
        actual_hash = sha256_of(path)
        if actual_hash != expected_hash:
            problems.append(
                f"hash mismatch for {rel}: expected {expected_hash}, got {actual_hash}"
            )

    return (len(problems) == 0), problems


if __name__ == "__main__":
    ok, problems = check()
    if ok:
        print("PROTECTED BENCHMARK INTEGRITY: OK — evaluation may proceed.")
        sys.exit(0)
    else:
        print("PROTECTED BENCHMARK INTEGRITY: FAILED CLOSED — evaluation refused.")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
