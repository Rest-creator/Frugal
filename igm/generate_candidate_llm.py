#!/usr/bin/env python3
"""IGM (Improvement Generation Mechanism) — LLM-backed generator (V1).

Same interface contract as generate_candidate.py (Docs/IGM-IEM-SPEC.md:
read findings + current tool source, read-only; write only to
candidates/), but the candidate body is produced by an actual Anthropic
API call instead of a hand-authored fix. This is the step 7 follow-up
named in README.md.

This candidate is NOT more trusted than the deterministic one. It still
goes through iem/run_evaluation.py like any other candidate — per
ARCHITECTURE.md's governing constraint, IGM's output (LLM-produced or not)
is untrusted input to IEM.

Usage: generate_candidate_llm.py <finding_id> [current_tool_path]
"""
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_backend import call_claude, LLMBackendError  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CANDIDATES_DIR = ROOT / "candidates"
DEFAULT_CURRENT_TOOL = ROOT / "lab" / "tools" / "baseline-ssh-detector" / "detect.py"

SYSTEM_PROMPT = """You are the Improvement Generation Mechanism (IGM) in Frugal, an \
AI-driven cybersecurity defence system. You are given a Finding describing a \
limitation in an existing security tool, and the tool's current source code. \
Your job is to propose ONE improved version of the tool that fixes the \
limitation.

Hard constraints:
- Preserve the tool's exact command-line contract: `python3 detect.py <log_path> \
[threshold]`, reading failed-login lines of the same format, defaulting \
threshold to 5 if omitted.
- Do not remove or weaken any existing detection capability the current tool \
already has — only add to it. A regression on behavior the tool already \
handled correctly is not an acceptable improvement.
- The tool must still print a line containing the literal substring "ALERT:" \
for each condition it flags, since that is how this pipeline's evaluation \
harness detects an alert.
- You are not the one who decides whether your proposal is accepted. An \
independent evaluator (IEM) will test it against protected benchmarks. Do \
not claim certainty about its effectiveness in your rationale — just explain \
your reasoning.

Respond with ONLY a single JSON object, no markdown fences, no commentary \
outside the JSON, with exactly these keys:
{
  "detector_source": "<the full, complete contents of the new detect.py file, as a single string>",
  "rationale": "<2-4 sentences explaining the change and why it addresses the finding>"
}
"""


def build_user_prompt(finding_text: str, current_tool_source: str) -> str:
    return (
        "## Finding\n\n"
        f"{finding_text}\n\n"
        "## Current tool source (lab/tools/baseline-ssh-detector/detect.py)\n\n"
        "```python\n"
        f"{current_tool_source}\n"
        "```\n"
    )


def main():
    if len(sys.argv) < 2:
        print("usage: generate_candidate_llm.py <finding_id> [current_tool_path]")
        sys.exit(1)

    finding_id = sys.argv[1]
    current_tool_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_CURRENT_TOOL

    finding_path = CANDIDATES_DIR / f"{finding_id}.md"
    if not finding_path.exists():
        print(f"finding not found: {finding_path}")
        sys.exit(1)

    finding_text = finding_path.read_text()
    current_tool_source = current_tool_path.read_text()

    user_prompt = build_user_prompt(finding_text, current_tool_source)

    try:
        response_text = call_claude(SYSTEM_PROMPT, user_prompt)
    except LLMBackendError as e:
        print(f"IGM (LLM-backed) refused to produce a candidate: {e}")
        sys.exit(1)

    try:
        parsed = json.loads(response_text)
        detector_source = parsed["detector_source"]
        rationale = parsed["rationale"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"IGM (LLM-backed) produced an unparseable response, discarding it: {e}")
        print("--- raw response ---")
        print(response_text)
        sys.exit(1)

    short_hash = hashlib.sha256(detector_source.encode()).hexdigest()[:8]
    candidate_id = f"CAND-LLM-{short_hash}"
    out_dir = CANDIDATES_DIR / candidate_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "detect.py").write_text(detector_source)

    metadata = {
        "id": candidate_id,
        "finding_id": finding_id,
        "target_tool": str(current_tool_path.relative_to(ROOT)),
        "diff_or_new_artifact": f"candidates/{candidate_id}/detect.py",
        "rationale": rationale,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generated_by": "igm/generate_candidate_llm.py (claude-sonnet-5-5)",
    }
    (out_dir / "candidate.json").write_text(json.dumps(metadata, indent=2) + "\n")

    print(f"Wrote candidate: {out_dir}")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
