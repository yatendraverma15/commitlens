import json
import subprocess
from pathlib import Path

from commitlens.config import CLAUDE_BIN
from commitlens.errors import APIError


def run_text_summary(
    *,
    system_prompt: str,
    user_text: str,
    model: str,
    timeout: int,
) -> str:
    """Invoke `claude -p` with a system prompt string and return the envelope's
    result text. Raises RuntimeError on failure — caller decides how to fall back."""
    if not CLAUDE_BIN:
        raise RuntimeError("Claude CLI not found")

    cmd = [
        CLAUDE_BIN, "-p",
        "--model", model,
        "--output-format", "json",
        "--system-prompt", system_prompt,
    ]
    result = subprocess.run(
        cmd,
        input=user_text,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip()[:200])
    envelope = json.loads(result.stdout)
    if envelope.get("is_error"):
        raise RuntimeError(str(envelope.get("result", ""))[:200])
    return (envelope.get("result") or "").strip()


def run_structured_analysis(
    *,
    system_prompt_file: Path,
    user_text: str,
    schema: dict,
    model: str,
    timeout: int,
    append_system: str | None = None,
) -> dict:
    """Invoke `claude -p` with a json schema and a system prompt loaded from file
    (the `-file` variant avoids the Windows argv/cp1252 transcoding bug).
    Returns the envelope's structured_output dict. Raises APIError on failure."""
    if not CLAUDE_BIN:
        raise APIError("Claude CLI not found. Ensure 'claude' is in your PATH.", status=500)

    cmd = [
        CLAUDE_BIN, "-p",
        "--model", model,
        "--output-format", "json",
        "--json-schema", json.dumps(schema),
        "--system-prompt-file", str(system_prompt_file),
    ]
    if append_system:
        cmd += ["--append-system-prompt", append_system]

    try:
        result = subprocess.run(
            cmd,
            input=user_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
        )
    except FileNotFoundError:
        raise APIError("Claude CLI not found. Ensure 'claude' is in your PATH.", status=500)
    except subprocess.TimeoutExpired:
        raise APIError("Claude analysis timed out.", status=504)

    if result.returncode != 0:
        raise APIError(f"Claude CLI failed: {result.stderr.strip()[:200]}", status=500)

    try:
        envelope = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise APIError("Could not parse Claude response.", status=500)

    if envelope.get("is_error"):
        raise APIError(envelope.get("result", "Claude returned an error."), status=500)

    structured = envelope.get("structured_output")
    if not structured:
        raise APIError("Claude returned no structured output.", status=500)

    return structured
