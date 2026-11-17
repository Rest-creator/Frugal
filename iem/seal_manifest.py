#!/usr/bin/env python3
"""Human-run-only tool: (re)computes the sha256 manifest for everything under
benchmarks/protected/ and writes benchmarks/protected/manifest.json.

Per Docs/DECISIONS_LOG.md ADR-002, this script is NOT invoked by IGM or IEM
at runtime, and neither service has write access to this directory or the
manifest it produces. It is run by a human when the protected suite is
deliberately changed, as part of a reviewed commit.
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


def build_manifest() -> dict:
    files = {}
    for path in sorted(PROTECTED_DIR.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            rel = path.relative_to(PROTECTED_DIR).as_posix()
            files[rel] = sha256_of(path)
    return {"files": files}


if __name__ == "__main__":
    manifest = build_manifest()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {MANIFEST_PATH} with {len(manifest['files'])} sealed file(s).")
    for rel, digest in manifest["files"].items():
        print(f"  {rel}: {digest}")
