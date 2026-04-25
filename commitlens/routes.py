from dataclasses import asdict

from flask import Blueprint, jsonify, render_template, request

from commitlens.analysis import analyze_commit, summarize_repo
from commitlens.config import INCLUDE_REPO_CONTEXT_IN_OUTPUT
from commitlens.errors import APIError
from commitlens.github import fetch_commit, fetch_diff, fetch_last_n, parse_repo_url

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}
    repo_url = data.get("repo_url", "").strip()
    mode = data.get("mode")
    sha = (data.get("sha") or "").strip()
    count = data.get("count")

    if not repo_url:
        raise APIError("Repository URL is required.")
    if mode not in ("specific", "last-n"):
        raise APIError("Invalid mode.")

    owner, repo = parse_repo_url(repo_url)

    if mode == "specific":
        if not sha:
            raise APIError("Commit SHA is required.")
        commits = [fetch_commit(owner, repo, sha)]
    else:
        try:
            n = max(1, min(10, int(count)))
        except (TypeError, ValueError):
            n = 5
        commits = fetch_last_n(owner, repo, n)

    repo_context = summarize_repo(owner, repo)

    results = []
    for commit in commits:
        diff = fetch_diff(owner, repo, commit.sha)
        analysis = analyze_commit(commit, diff, repo_context)
        results.append({"commit": asdict(commit), "analysis": analysis})

    response = {"results": results}
    if INCLUDE_REPO_CONTEXT_IN_OUTPUT and repo_context:
        response["repo_context"] = repo_context
    return jsonify(response)
