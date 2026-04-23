import json
import re
import shutil
import subprocess
import urllib.request
import urllib.error
from flask import Flask, render_template, request, jsonify

CLAUDE_BIN = shutil.which("claude") or shutil.which("claude.cmd")

app = Flask(__name__)

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

SYSTEM_PROMPT = (
    "You are a Senior SDET. Analyze the provided git commit and return a JSON object "
    "matching the provided schema. No BDD. No Given/When/Then. Plain language only. "
    "Test scenarios should describe inputs and expected results."
)


class APIError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def parse_repo_url(url):
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    match = re.search(r"github\.com[:/]([^/]+)/([^/]+)", url)
    if not match:
        raise APIError("Invalid GitHub URL.")
    return match.group(1), match.group(2)


def github_get(url, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "CommitLens"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise APIError("Repository or commit not found. Check the URL or SHA.")
        if e.code in (403, 429):
            raise APIError("GitHub API rate limit reached. Try again later.")
        raise APIError(f"GitHub API error ({e.code}).")
    except urllib.error.URLError:
        raise APIError("Network error. Check your connection.", status=502)


def fetch_commit(owner, repo, sha):
    data = json.loads(github_get(f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"))
    return {
        "sha": data["sha"],
        "message": data["commit"]["message"].split("\n")[0],
        "author": data["commit"]["author"]["name"],
        "date": data["commit"]["author"]["date"],
    }


def fetch_last_n(owner, repo, count):
    data = json.loads(github_get(f"https://api.github.com/repos/{owner}/{repo}/commits?per_page={count}"))
    return [fetch_commit(owner, repo, c["sha"]) for c in data]


def fetch_diff(owner, repo, sha):
    return github_get(
        f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}",
        accept="application/vnd.github.diff",
    )


def truncate_diff(diff, max_chars=40000):
    if len(diff) <= max_chars:
        return diff
    return diff[:max_chars] + "\n\n[diff truncated — too large]"


def analyze_with_claude(commit, diff):
    user_message = (
        f"Commit SHA: {commit['sha']}\n"
        f"Author: {commit['author']}\n"
        f"Date: {commit['date']}\n"
        f"Message: {commit['message']}\n\n"
        f"Diff:\n{truncate_diff(diff)}"
    )

    if not CLAUDE_BIN:
        raise APIError("Claude CLI not found. Ensure 'claude' is in your PATH.", status=500)

    cmd = [
        CLAUDE_BIN, "-p",
        "--model", "opus",
        "--output-format", "json",
        "--json-schema", json.dumps(ANALYSIS_SCHEMA),
        "--system-prompt", SYSTEM_PROMPT,
    ]

    try:
        result = subprocess.run(
            cmd,
            input=user_message,
            capture_output=True,
            text=True,
            timeout=180,
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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}
    repo_url = data.get("repo_url", "").strip()
    mode = data.get("mode")
    sha = (data.get("sha") or "").strip()
    count = data.get("count")

    if not repo_url:
        return jsonify({"error": "Repository URL is required."}), 400
    if mode not in ("specific", "last-n"):
        return jsonify({"error": "Invalid mode."}), 400

    try:
        owner, repo = parse_repo_url(repo_url)

        if mode == "specific":
            if not sha:
                return jsonify({"error": "Commit SHA is required."}), 400
            commits = [fetch_commit(owner, repo, sha)]
        else:
            try:
                n = max(1, min(10, int(count)))
            except (TypeError, ValueError):
                n = 5
            commits = fetch_last_n(owner, repo, n)

        results = []
        for commit in commits:
            diff = fetch_diff(owner, repo, commit["sha"])
            analysis = analyze_with_claude(commit, diff)
            results.append({"commit": commit, "analysis": analysis})

        return jsonify({"results": results})

    except APIError as e:
        return jsonify({"error": e.message}), e.status
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)[:200]}"}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)
