import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = REPO_ROOT / ".github_token"
PROMPT_PATH = REPO_ROOT / "system_prompt.md"


def _load_github_token() -> str | None:
    if TOKEN_FILE.exists():
        for line in TOKEN_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line == "PASTE_GITHUB_TOKEN_HERE":
                continue
            return line
    return os.environ.get("GITHUB_TOKEN", "").strip() or None


CLAUDE_BIN = shutil.which("claude") or shutil.which("claude.cmd")
GITHUB_TOKEN = _load_github_token()

INCLUDE_API_DETAILS = False
INCLUDE_REPO_CONTEXT_IN_OUTPUT = False
REPO_CONTEXT_TTL = 3600
README_MAX_CHARS = 20000
DIFF_MAX_CHARS = 40000

NO_API_APPEND = (
    "RUNTIME OVERRIDE: exclude all API-level content from qa_summary, impacted_areas, "
    "areas_needing_testing, and test_scenarios. Do NOT mention HTTP methods, endpoints, "
    "URLs, status codes, request or response JSON shapes, field names, or header values. "
    "Express every behavior in user-facing functional terms only: what the user does, what "
    "they see, and what the application does for them. Validation failures must be described "
    "as the message or UI state the user observes, not as HTTP codes."
)

REPO_SUMMARY_SYSTEM_PROMPT = (
    "You summarize what a software project does from an end user's perspective. "
    "You will receive a repository name plus optional description, topics, primary language, "
    "and README text. Return 4 to 8 plain-language sentences describing: what the application "
    "is, what users can do with it, what they see, and what they accomplish. "
    "Rules: no code paths, no file or module names, no class or function names, no HTTP methods, "
    "no endpoints, no status codes, no request or response shapes, no library or framework "
    "internals. Use plain English. Return only the summary text with no preamble, no markdown "
    "headings, no bullet list, no code fences."
)

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "qa_summary": {"type": "string"},
        "risk_level": {"type": "string", "enum": ["Low", "Medium", "High", "Critical"]},
        "risk_reasoning": {"type": "string"},
        "impacted_areas": {"type": "array", "items": {"type": "string"}},
        "areas_needing_testing": {"type": "array", "items": {"type": "string"}},
        "test_scenarios": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "qa_summary",
        "risk_level",
        "risk_reasoning",
        "impacted_areas",
        "areas_needing_testing",
        "test_scenarios",
    ],
}


if not PROMPT_PATH.exists():
    raise RuntimeError(
        f"System prompt file not found at {PROMPT_PATH}. "
        "Create system_prompt.md at the repository root."
    )
