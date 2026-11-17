"""Minimal Anthropic Messages API client for IGM, stdlib-only (no `pip`
available in this environment, and no `anthropic` package installed — this
avoids depending on either).

Reads ANTHROPIC_API_KEY from the environment. Raises a clear error if it's
missing rather than silently falling back to the deterministic generator —
IGM's own caller decides whether that's fatal or a reason to fall back.
"""
import json
import os
import urllib.request
import urllib.error

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = os.environ.get("IGM_MODEL", "claude-sonnet-5-5")


class LLMBackendError(RuntimeError):
    pass


def call_claude(system: str, user_prompt: str, model: str = DEFAULT_MODEL, max_tokens: int = 4096) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise LLMBackendError(
            "ANTHROPIC_API_KEY is not set. IGM's LLM-backed generation path "
            "requires it; refusing to fabricate a response."
        )

    payload = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user_prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=payload,
        method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise LLMBackendError(f"Anthropic API error {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise LLMBackendError(f"Could not reach Anthropic API: {e}") from e

    try:
        return "".join(block["text"] for block in body["content"] if block.get("type") == "text")
    except (KeyError, TypeError) as e:
        raise LLMBackendError(f"Unexpected response shape from Anthropic API: {body}") from e
