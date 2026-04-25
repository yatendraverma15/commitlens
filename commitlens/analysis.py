import logging

from commitlens.cache import TTLCache
from commitlens.claude import run_structured_analysis, run_text_summary
from commitlens.config import (
    ANALYSIS_SCHEMA,
    CLAUDE_BIN,
    DIFF_MAX_CHARS,
    INCLUDE_API_DETAILS,
    NO_API_APPEND,
    PROMPT_PATH,
    REPO_CONTEXT_TTL,
    REPO_SUMMARY_SYSTEM_PROMPT,
)
from commitlens.github import fetch_readme, fetch_repo_meta
from commitlens.models import Commit

logger = logging.getLogger(__name__)
_repo_cache: TTLCache[str] = TTLCache(REPO_CONTEXT_TTL)


def _truncate_diff(diff: str) -> str:
    if len(diff) <= DIFF_MAX_CHARS:
        return diff
    return diff[:DIFF_MAX_CHARS] + "\n\n[diff truncated — too large]"


def _describe_meta(owner: str, repo: str, meta: dict) -> str:
    lines = [f"Repository: {owner}/{repo}"]
    if meta.get("description"):
        lines.append(f"Description: {meta['description']}")
    if meta.get("language"):
        lines.append(f"Primary language: {meta['language']}")
    if meta.get("topics"):
        lines.append("Topics: " + ", ".join(meta["topics"]))
    return "\n".join(lines)


def summarize_repo(owner: str, repo: str) -> str:
    key = (owner.lower(), repo.lower())
    cached = _repo_cache.get(key)
    if cached is not None:
        logger.info("repo context: hit (%s/%s)", owner, repo)
        return cached

    meta = fetch_repo_meta(owner, repo)
    readme = fetch_readme(owner, repo)

    if not meta and not readme:
        logger.info("repo context: skipped (%s/%s) — no meta or README", owner, repo)
        _repo_cache.set(key, "")
        return ""

    if not CLAUDE_BIN:
        summary = meta.get("description", "")
        _repo_cache.set(key, summary)
        return summary

    user_text = _describe_meta(owner, repo, meta)
    if readme:
        user_text += f"\n\nREADME:\n{readme}"

    try:
        summary = run_text_summary(
            system_prompt=REPO_SUMMARY_SYSTEM_PROMPT,
            user_text=user_text,
            model="sonnet",
            timeout=60,
        )
        if not summary:
            raise RuntimeError("empty summary")
        logger.info("repo context: miss (%s/%s) — summarized", owner, repo)
    except Exception as e:
        summary = meta.get("description", "")
        logger.warning("repo context: fallback (%s/%s) — %s", owner, repo, str(e)[:120])

    _repo_cache.set(key, summary)
    return summary


def analyze_commit(commit: Commit, diff: str, repo_context: str = "") -> dict:
    commit_block = (
        f"Commit SHA: {commit.sha}\n"
        f"Author: {commit.author}\n"
        f"Date: {commit.date}\n"
        f"Message: {commit.message}\n\n"
        f"Diff:\n{_truncate_diff(diff)}"
    )
    user_text = (
        f"## Repository Context\n{repo_context}\n\n## Commit\n{commit_block}"
        if repo_context
        else commit_block
    )

    return run_structured_analysis(
        system_prompt_file=PROMPT_PATH,
        user_text=user_text,
        schema=ANALYSIS_SCHEMA,
        model="opus",
        timeout=180,
        append_system=None if INCLUDE_API_DETAILS else NO_API_APPEND,
    )
