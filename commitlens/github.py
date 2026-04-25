import base64
import json
import re
import urllib.error
import urllib.request

from commitlens.config import GITHUB_TOKEN, README_MAX_CHARS
from commitlens.errors import APIError
from commitlens.models import Commit


def parse_repo_url(url: str) -> tuple[str, str]:
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    match = re.search(r"github\.com[:/]([^/]+)/([^/]+)", url)
    if not match:
        raise APIError("Invalid GitHub URL.")
    return match.group(1), match.group(2)


def _github_get(url: str, accept: str = "application/vnd.github+json") -> str:
    headers = {"Accept": accept, "User-Agent": "CommitLens"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise APIError("Repository or commit not found. Check the URL or SHA.")
        if e.code == 401:
            raise APIError("GitHub token is invalid or expired. Update .github_token.")
        if e.code in (403, 429):
            raise APIError("GitHub API rate limit reached. Try again later.")
        raise APIError(f"GitHub API error ({e.code}).")
    except urllib.error.URLError:
        raise APIError("Network error. Check your connection.", status=502)


def fetch_commit(owner: str, repo: str, sha: str) -> Commit:
    data = json.loads(_github_get(f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"))
    return Commit(
        sha=data["sha"],
        message=data["commit"]["message"].split("\n")[0],
        author=data["commit"]["author"]["name"],
        date=data["commit"]["author"]["date"],
    )


def fetch_last_n(owner: str, repo: str, count: int) -> list[Commit]:
    data = json.loads(
        _github_get(f"https://api.github.com/repos/{owner}/{repo}/commits?per_page={count}")
    )
    return [fetch_commit(owner, repo, c["sha"]) for c in data]


def fetch_diff(owner: str, repo: str, sha: str) -> str:
    return _github_get(
        f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}",
        accept="application/vnd.github.diff",
    )


def fetch_repo_meta(owner: str, repo: str) -> dict:
    try:
        data = json.loads(_github_get(f"https://api.github.com/repos/{owner}/{repo}"))
    except Exception:
        return {}
    return {
        "description": (data.get("description") or "").strip(),
        "topics": data.get("topics") or [],
        "language": (data.get("language") or "").strip(),
    }


def fetch_readme(owner: str, repo: str) -> str:
    try:
        data = json.loads(_github_get(f"https://api.github.com/repos/{owner}/{repo}/readme"))
        content = data.get("content") or ""
        encoding = data.get("encoding") or "base64"
        if encoding != "base64":
            return ""
        text = base64.b64decode(content).decode("utf-8", errors="replace")
    except Exception:
        return ""
    if len(text) > README_MAX_CHARS:
        text = text[:README_MAX_CHARS] + "\n\n[README truncated]"
    return text
