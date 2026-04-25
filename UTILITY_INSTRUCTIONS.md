# CommitLens — Build Playbook

A reproducible, phased prompt for building CommitLens from an empty directory. Each phase is a self-contained instruction you can hand to Claude Code (or any capable coding assistant) sequentially.

---

## What you are building

**CommitLens** is a small Flask web app that analyzes GitHub commits for QA risk and produces structured output: a QA summary, a risk level, impacted user-facing areas, areas needing testing, and concrete test scenarios. It shells out to the `claude` CLI (`claude -p`) so the developer's existing Claude Code session provides authentication — the app itself **never handles an Anthropic API key**. The per-commit analysis prompt lives in a separate file (`system_prompt.md`) so it can be iterated on without touching code.

### Primary capabilities

- Analyze one specific commit by SHA, or the last N commits (1–10) of a public GitHub repo.
- Optional GitHub token support for lifted rate limits (read from `.github_token` file or `GITHUB_TOKEN` env var).
- Automatic **repository context summarization**: on first request for a repo, the backend fetches metadata + README and asks Claude Sonnet for a 4–8 sentence user-facing summary, cached for 1 hour. This context is injected into every commit analysis so the model knows the domain instead of inferring it from a diff alone.
- **System prompt externalized** to `system_prompt.md` — loaded via `claude --system-prompt-file` at request time.
- Two runtime toggles in `commitlens/config.py`:
  - `INCLUDE_API_DETAILS` — when `False` (default), suppresses HTTP/endpoint/status-code details from the output via `--append-system-prompt`.
  - `INCLUDE_REPO_CONTEXT_IN_OUTPUT` — when `True`, the repo-context summary is returned in the `/analyze` response and rendered as a card in the UI.
- Frontend preserves **up to 5 prior analyses** in the output window; re-analyzing an existing commit replaces its card; a Clear button wipes the output window.

### Tech stack (deliberate choices)

- **Python 3.10+** with standard library only (`urllib`, `subprocess`, `logging`, `dataclasses`) — no heavy dependencies.
- **Flask** as the only third-party Python dependency. Used with an app factory and a blueprint.
- **Claude CLI** (`claude -p`) as the LLM interface — no `anthropic` SDK, no API keys handled by the app.
- **GitHub REST API** via `urllib.request` — no `PyGithub`, no `requests`.
- **Vanilla JS + CSS** for the frontend — no build step, no framework. Static assets served from `static/`.

---

## Target project layout

```
commitlens/                         # repo root
├── app.py                          # thin entrypoint: create_app() and run
├── requirements.txt                # single line: flask
├── system_prompt.md                # QA analyst persona + output contract (SEE BELOW)
├── CLAUDE.md                       # guidance for Claude Code sessions
├── README.md                       # setup and usage
├── UTILITY_INSTRUCTIONS.md         # this file
├── .gitignore                      # ignores __pycache__, .venv, .github_token
├── .github_token                   # optional, git-ignored, line-delimited token file
├── commitlens/                     # Python package
│   ├── __init__.py                 # create_app() factory + logging setup
│   ├── config.py                   # paths, toggles, schema, system-prompt constants
│   ├── errors.py                   # APIError + register_error_handlers()
│   ├── models.py                   # @dataclass Commit
│   ├── cache.py                    # TTLCache[T] helper
│   ├── github.py                   # parse_repo_url, fetch_commit, fetch_last_n, fetch_diff, fetch_repo_meta, fetch_readme
│   ├── claude.py                   # subprocess wrappers: run_text_summary, run_structured_analysis
│   ├── analysis.py                 # orchestration: summarize_repo, analyze_commit
│   └── routes.py                   # Flask Blueprint: GET /, POST /analyze
├── static/
│   ├── app.css                     # all styles (extracted from template)
│   └── app.js                      # all client-side behavior
└── templates/
    └── index.html                  # skeleton — references static/ files
```

---

## Prerequisites

1. Python 3.10 or newer.
2. The `claude` CLI installed and already authenticated (run `claude` once interactively before starting). The app will **not** work without a logged-in Claude Code session — the subprocess reuses it.
3. (Optional) A GitHub personal access token if you expect to exceed the unauthenticated rate limit of 60 requests/hour.

---

## Phase 1 — Scaffold the project

```
Create an empty Python project named commitlens with this structure:

commitlens/
├── app.py                          (empty placeholder)
├── requirements.txt                (single line: flask)
├── .gitignore                      (ignore: __pycache__/, *.pyc, .venv/, venv/, .env, .github_token)
├── README.md                       (brief: what it does, how to run: pip install -r requirements.txt then python app.py → http://127.0.0.1:5001)
├── system_prompt.md                (empty placeholder — to be written in Phase 9)
├── commitlens/                     (empty directory with empty __init__.py)
├── static/                         (empty directory)
└── templates/                      (empty directory)

Do not implement any features yet. Do not commit yet.
```

---

## Phase 2 — Package core: config, models, cache, errors, factory

```
Inside the commitlens/ package, create these files.

1. commitlens/config.py — loads configuration and declares all constants:
   - REPO_ROOT = Path(__file__).resolve().parent.parent
   - TOKEN_FILE = REPO_ROOT / ".github_token"
   - PROMPT_PATH = REPO_ROOT / "system_prompt.md"
   - _load_github_token() reads .github_token (first non-empty, non-comment,
     non-placeholder line) then falls back to env var GITHUB_TOKEN, else None.
   - CLAUDE_BIN = shutil.which("claude") or shutil.which("claude.cmd")
   - GITHUB_TOKEN = _load_github_token()
   - Toggles (module-level constants):
       INCLUDE_API_DETAILS = False
       INCLUDE_REPO_CONTEXT_IN_OUTPUT = False
   - Size limits:
       REPO_CONTEXT_TTL = 3600       # seconds
       README_MAX_CHARS = 20000
       DIFF_MAX_CHARS = 40000
   - NO_API_APPEND: ASCII-only string appended to the system prompt via
     --append-system-prompt when INCLUDE_API_DETAILS is False. It bans
     HTTP methods, endpoints, URLs, status codes, and request/response
     JSON shapes from the output and demands user-facing phrasing only.
   - REPO_SUMMARY_SYSTEM_PROMPT: a short (ASCII-only) system prompt for
     Claude Sonnet explaining how to summarize a repo for the user: 4–8
     plain-language sentences describing what the app is, what users do,
     what they see. No code paths, no module or function names, no
     HTTP details.
   - ANALYSIS_SCHEMA: dict matching the JSON schema for the six required
     output fields:
       qa_summary (string)
       risk_level (string enum: Low | Medium | High | Critical)
       risk_reasoning (string)
       impacted_areas (array of strings)
       areas_needing_testing (array of strings)
       test_scenarios (array of strings)
   - At import time, raise RuntimeError if PROMPT_PATH does not exist
     (fail fast so the dev fixes it immediately).

2. commitlens/errors.py — APIError + Flask error handler registration:
   - class APIError(Exception) with __init__(self, message, status=400).
   - register_error_handlers(app) registers:
       * @app.errorhandler(APIError) → return jsonify({"error": e.message}), e.status
       * @app.errorhandler(Exception) → logger.exception(...); return jsonify
         ({"error": "Unexpected error: <truncated>"}), 500

3. commitlens/models.py — one frozen dataclass:
   @dataclass(frozen=True)
   class Commit:
       sha: str
       message: str
       author: str
       date: str

4. commitlens/cache.py — a minimal TTL cache generic in its value type:
   class TTLCache(Generic[T]):
       __init__(ttl_seconds): store ttl, empty dict
       get(key) → Optional[T]: return None if absent or expired (evict on expiry)
       set(key, value): store with expiry = now + ttl
   Keys should be hashable (tuples work).

5. commitlens/__init__.py — logging setup + Flask app factory:
   - _setup_logging() uses logging.basicConfig with level=INFO, format
     "[%(asctime)s] %(levelname)s %(name)s: %(message)s", datefmt "%H:%M:%S",
     force=True.
   - create_app() → Flask:
       * call _setup_logging()
       * construct Flask with static_folder and template_folder
         pointing at the repo root static/ and templates/ directories
         (Path-based so it works regardless of CWD)
       * import GITHUB_TOKEN and log whether auth is enabled or disabled
       * register_error_handlers(app)
       * app.register_blueprint(bp) — bp defined in routes.py (Phase 6)
       * return app

Do not commit yet.
```

---

## Phase 3 — GitHub client

```
Create commitlens/github.py. It uses only urllib.request + urllib.error + json
+ base64 + re from the standard library. No third-party HTTP client.

Functions to implement:

1. parse_repo_url(url: str) -> tuple[str, str]
   - Strip whitespace and trailing slash. If url ends with ".git", drop it.
   - Regex-match "github.com[:/]([^/]+)/([^/]+)" and return (owner, repo).
   - On no match: raise APIError("Invalid GitHub URL.").

2. _github_get(url, accept="application/vnd.github+json") -> str
   - Build request with headers Accept, User-Agent=CommitLens,
     and Authorization: Bearer <token> if GITHUB_TOKEN is set.
   - urlopen with timeout 30. Return decoded body.
   - Error mapping (raise APIError with appropriate message and status):
       404 → "Repository or commit not found. Check the URL or SHA."
       401 → "GitHub token is invalid or expired. Update .github_token."
       403 or 429 → "GitHub API rate limit reached. Try again later."
       Other HTTPError → "GitHub API error (<code>)."
       URLError → "Network error. Check your connection." with status=502.

3. fetch_commit(owner, repo, sha) -> Commit
   - GET /repos/{owner}/{repo}/commits/{sha}
   - Return Commit(sha, message=first line of commit message, author=name, date=author date).

4. fetch_last_n(owner, repo, count) -> list[Commit]
   - GET /repos/{owner}/{repo}/commits?per_page={count}
   - For each returned commit, call fetch_commit(owner, repo, c["sha"]) so
     the full Commit dataclass is built consistently.

5. fetch_diff(owner, repo, sha) -> str
   - GET /repos/{owner}/{repo}/commits/{sha} with
     Accept: application/vnd.github.diff
   - Return raw text.

6. fetch_repo_meta(owner, repo) -> dict
   - GET /repos/{owner}/{repo}
   - Return {"description": ..., "topics": [...], "language": ...}.
   - On any exception, return empty dict (do NOT raise — repo context is best-effort).

7. fetch_readme(owner, repo) -> str
   - GET /repos/{owner}/{repo}/readme → JSON with base64-encoded content.
   - Decode to UTF-8 (errors="replace").
   - If length > README_MAX_CHARS, truncate and append "\n\n[README truncated]".
   - On any exception, return "".

Do not commit yet.
```

---

## Phase 4 — Claude CLI subprocess wrapper

```
Create commitlens/claude.py. This module isolates the subprocess plumbing from
the orchestration logic so the calling code never constructs argv manually.

Two functions:

1. run_text_summary(*, system_prompt, user_text, model, timeout) -> str
   Used for free-form summaries (repo context).
   - argv: [CLAUDE_BIN, "-p", "--model", model, "--output-format", "json",
           "--system-prompt", system_prompt]
   - subprocess.run with input=user_text, text=True, encoding="utf-8",
     capture_output=True, timeout=timeout.
   - On non-zero returncode or envelope.is_error: raise RuntimeError with
     truncated error text (caller decides how to fall back).
   - Parse envelope (json.loads(stdout)) and return (envelope["result"] or "").strip().

2. run_structured_analysis(*, system_prompt_file: Path, user_text, schema: dict,
                           model, timeout, append_system: str | None) -> dict
   Used for per-commit analysis (schema-constrained output).
   - argv: [CLAUDE_BIN, "-p", "--model", model, "--output-format", "json",
           "--json-schema", json.dumps(schema),
           "--system-prompt-file", str(system_prompt_file)]
     If append_system is non-None, append ["--append-system-prompt", append_system].
   - On FileNotFoundError → raise APIError("Claude CLI not found...", status=500).
   - On TimeoutExpired → raise APIError("Claude analysis timed out.", status=504).
   - On non-zero returncode → raise APIError("Claude CLI failed: <stderr>", status=500).
   - On JSON parse error → raise APIError("Could not parse Claude response.", status=500).
   - On envelope.is_error → raise APIError(envelope.result, status=500).
   - Return envelope["structured_output"] (a dict).
   - If structured_output is missing/empty → raise APIError("Claude returned no structured output.", status=500).

CRITICAL Windows gotcha (document in a comment on the run_structured_analysis
function):
   On Windows, shutil.which("claude") usually resolves to claude.CMD — a batch
   wrapper. When Python's subprocess passes a long argv string to a .CMD,
   Windows transcodes each argument from Unicode to the console codepage
   (cp1252 in most US/English locales). system_prompt.md contains characters
   outside cp1252 (≤, →, em dashes, curly quotes) which would silently
   corrupt if passed inline via --system-prompt. ALWAYS pass the prompt file
   path via --system-prompt-file instead; the path is ASCII, and claude reads
   the file as UTF-8 itself. --append-system-prompt is acceptable ONLY because
   NO_API_APPEND is pure ASCII. Any new runtime-constructed prompt content
   that may contain non-ASCII characters MUST be written to a file and passed
   with the -file variant.

Do not commit yet.
```

---

## Phase 5 — Analysis orchestration

```
Create commitlens/analysis.py. This is the only module that knows how to
compose a repo-context prompt and a per-commit prompt. It uses cache.py,
claude.py, and github.py.

Module-level:
   logger = logging.getLogger(__name__)
   _repo_cache: TTLCache[str] = TTLCache(REPO_CONTEXT_TTL)

Helpers:

   _truncate_diff(diff) -> str
     If len <= DIFF_MAX_CHARS return as-is; else return first DIFF_MAX_CHARS
     chars plus "\n\n[diff truncated — too large]".

   _describe_meta(owner, repo, meta) -> str
     Build a few lines: "Repository: owner/repo", optional "Description: ...",
     "Primary language: ...", "Topics: a, b, c".

Public functions:

1. summarize_repo(owner, repo) -> str
   Caches a 4–8 sentence user-facing summary of the repo for 1 hour.
   - key = (owner.lower(), repo.lower())
   - If cache hit (non-None, including empty string): log "repo context: hit (owner/repo)"
     and return cached.
   - Else fetch_repo_meta and fetch_readme.
     * If both are empty/missing: log "repo context: skipped ... — no meta or README",
       cache "", return "".
     * If CLAUDE_BIN is not available: cache meta.description, return that.
   - Otherwise build user_text from _describe_meta + optional "\n\nREADME:\n" + readme.
   - Call claude.run_text_summary(system_prompt=REPO_SUMMARY_SYSTEM_PROMPT, model="sonnet",
     timeout=60).
     * On any exception: fall back to meta.description (possibly ""), log warning
       "repo context: fallback ... — <exc>" (truncate to 120 chars).
     * On success: log "repo context: miss ... — summarized".
   - Cache the summary and return it.

2. analyze_commit(commit: Commit, diff: str, repo_context: str = "") -> dict
   - Build commit_block with SHA, Author, Date, Message, then "\n\nDiff:\n" + truncated diff.
   - If repo_context is non-empty: user_text = "## Repository Context\n" + repo_context +
     "\n\n## Commit\n" + commit_block. Else user_text = commit_block.
   - Call claude.run_structured_analysis:
       system_prompt_file = PROMPT_PATH
       schema = ANALYSIS_SCHEMA
       model = "opus"
       timeout = 180
       append_system = None if INCLUDE_API_DETAILS else NO_API_APPEND
   - Return the structured_output dict unchanged.

Note: analyze_commit never mutates or validates the six-field shape — the
--json-schema flag enforces it at the CLI boundary. The frontend assumes the
shape and will fail visibly if it ever changes.

Do not commit yet.
```

---

## Phase 6 — Routes blueprint

```
Create commitlens/routes.py. Use Flask's Blueprint pattern so app.py can stay
thin and tests (if added later) can import the blueprint without starting a
server.

from flask import Blueprint, jsonify, render_template, request

bp = Blueprint("main", __name__)

@bp.route("/")
def index():
    return render_template("index.html")

@bp.route("/analyze", methods=["POST"])
def analyze():
    Parse JSON body. Required: repo_url (non-empty). mode ∈ {"specific", "last-n"}.
    - If repo_url missing → raise APIError("Repository URL is required.").
    - If mode invalid → raise APIError("Invalid mode.").

    owner, repo = parse_repo_url(repo_url)

    if mode == "specific":
        sha = data.get("sha", "").strip()
        if not sha → raise APIError("Commit SHA is required.")
        commits = [fetch_commit(owner, repo, sha)]
    else:
        try: n = max(1, min(10, int(count)))
        except (TypeError, ValueError): n = 5
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

Do NOT wrap the body in a try/except — the errors module's registered handlers
will format APIError and generic Exception as JSON responses automatically.

Do not commit yet.
```

---

## Phase 7 — Frontend (single-page UI)

The frontend is a minimal single-page app: one analyze form, one output card with up to 5 collapsible commit cards, plus an optional repository context card at the top when the toggle is on.

```
Create these three files. Use vanilla JS and CSS only — no framework, no bundler.

1. templates/index.html
   - Standard HTML5 skeleton. <title>CommitLens — QA Commit Analyzer</title>.
   - <link rel="stylesheet" href="{{ url_for('static', filename='app.css') }}" />
   - <header> with h1 "CommitLens" and a short subtitle.
   - <main> with two cards:
     a. INPUT CARD:
        - <h2>Analyze Commits</h2>
        - Text input for GitHub repo URL (placeholder "https://github.com/owner/repo")
        - Radio group: "Specific Commit" (default) / "Last N Commits"
        - #sha-field with text input (visible by default)
        - #n-field with number input 1–10, default 5 (hidden by default, .hidden class)
        - #analyze-btn submit button
     b. OUTPUT CARD (#output-card):
        - #action-bar (hidden by default) containing a Clear button (.btn-secondary).
        - #empty-state placeholder text.
        - #repo-context-card (.hidden by default) containing a "Repository Context"
          section label and a #repo-context-text div.
        - #results-section (.hidden until first analysis) — commit cards are appended here.
   - <footer> with "Powered by Claude & GitHub API".
   - <script src="{{ url_for('static', filename='app.js') }}"></script>

2. static/app.css
   - Clean, minimal, professional: light slate background, card-based layout,
     max-width 820px centered main, rounded corners, subtle shadow.
   - Risk badges: .risk-low (green), .risk-medium (orange), .risk-high (red),
     .risk-critical (dark red on light red).
   - .hidden { display: none !important; }
   - Spinner keyframes for the loading indicator.
   - Explicit styles for #repo-context-card (subtle slate background, rounded).

3. static/app.js — implement this behavior (all in one file, no modules):

   a. Radio toggle: show #sha-field for "specific", #n-field for "last-n".

   b. Render helpers:
      - renderRepoContext(ctx): if non-empty, fill #repo-context-text and unhide
        #repo-context-card; else clear and hide.
      - renderCommitCard(commit, analysis) → HTML string with:
         * Collapsible header: short SHA + author + formatted date + a small
           "Copy" button (with an inline SVG icon) + a ▼ toggle glyph.
           Clicking the header (but NOT the Copy button) toggles the body.
         * Body: commit message (italic), then five sections in order:
           "QA Summary" (escaped plain text), "Risk Level" (badge + reasoning),
           "Impacted Functional Areas" (bullet list), "Areas Needing Testing"
           (bullet list), "Test Scenario Suggestions" (numbered list).
         * renderList(items, ordered) returns "None." placeholder when empty.
         * escapeHtml() to sanitize all interpolated text.

   c. Output-history behavior (cap = 5):
      - On successful analysis, PREPEND new cards to #results-section.
      - Before prepending, dedupe: remove any existing card whose short SHA
        is in the incoming batch.
      - trimResults(): keep only first 5 .commit-card elements.
      - Spinner and error banners are inserted at the top of #results-section
        via removeTransient() + insertBefore; they do NOT clear existing cards.

   d. Clear button: reset form inputs, uncheck all radios (default "specific"),
      show #sha-field, hide #n-field, call showEmpty() which also calls
      renderRepoContext("").

   e. Per-commit Copy button: walk the card's section labels and copy a
      plain-text report to clipboard; briefly flip button label to "Copied!".

   f. Analyze button click:
      - Read repo_url, mode, sha or count; validate; show spinner with text
        "Fetching commits and analyzing with Claude… this can take 10–60 seconds."
      - POST to /analyze with JSON body.
      - If !res.ok: showError(data.error).
      - Else: removeTransient(); renderRepoContext(data.repo_context || "");
        render new cards (prepend newest-first to preserve batch order), then
        trimResults(); show the Clear action bar.

Do not commit yet.
```

---

## Phase 8 — Thin entrypoint

```
At the repo root, replace app.py with the minimal entrypoint:

    from commitlens import create_app

    app = create_app()

    if __name__ == "__main__":
        app.run(host="127.0.0.1", port=5001, debug=False)

Verify boot: `python app.py` should log

    [HH:MM:SS] INFO commitlens: GitHub auth: disabled (public repos only)
    [HH:MM:SS] INFO werkzeug: ...Running on http://127.0.0.1:5001

Hit http://127.0.0.1:5001 — the input form renders. /static/app.css and
/static/app.js should both return 200.

Now commit the scaffolded app:
    git add .
    git commit -m "feat: scaffold CommitLens Flask app with factory layout"
```

---

## Phase 9 — The analysis prompt

Do **not** inline the QA analyst system prompt in code. It is maintained as a separate Markdown file that the app loads at request time via `claude --system-prompt-file`. This lets you iterate on the prompt without redeploying or restarting.

**The source of truth for the per-commit analysis prompt is `system_prompt.md` at the repo root.** Copy it from [`system_prompt.md`](./system_prompt.md) — it defines:

- The Senior SDET persona and JSON-only output contract.
- How to treat the injected `## Repository Context` block when present (framing only, never summarized in output).
- How to infer the domain from the diff when no context is present — file paths, symbol names, imports, visible strings, the commit message.
- **Tool and framework awareness**: recognizing Ranorex, Selenium, Playwright, Cypress, pytest, JUnit, React, Django, Docker, Kubernetes, etc., and framing test scenarios in tool-appropriate language. Tools are explicitly exempted from the "no code-layer references" rule.
- Strict length caps: `qa_summary` 2–3 sentences / ≤60 words, `risk_reasoning` one sentence ≤25 words, test_scenarios ≤15 words each in `<user action> → <observable outcome>` form.
- Exclude list: no file paths, no code-layer references, no concurrency/performance/security/CSS/test-infra topics unless the commit is explicitly about one of them.
- Risk level anchors for Low / Medium / High / Critical.

When you modify the prompt, restart is not strictly required — the file is re-read on every `/analyze` call — but restart anyway to clear any in-memory repo-context cache between tests.

---

## Phase 10 — Runtime toggles (optional overrides)

Both live in `commitlens/config.py`:

### `INCLUDE_API_DETAILS` (default `False`)

When `False`, `NO_API_APPEND` is passed to `claude` via `--append-system-prompt`. This is an ASCII-only string that forbids HTTP methods, endpoints, status codes, and request/response JSON shapes from appearing in the output — forcing all validation and data-retrieval wording into user-visible terms ("the user sees X", not "GET /foo returns X"). Flip to `True` when the audience is API-savvy and wants endpoint-level detail back.

### `INCLUDE_REPO_CONTEXT_IN_OUTPUT` (default `False`)

When `True`, the Sonnet-generated repo summary is included in the `/analyze` JSON response as a top-level `repo_context` field. The frontend's `renderRepoContext()` picks it up and shows the `#repo-context-card` above the commit cards. Off by default because the summary is purely internal framing for the model; some users don't want it cluttering the UI.

Both toggles take effect on server restart — Flask loads `config.py` at import time and the values are captured into the modules that import them.

---

## Phase 11 — End-to-end verification

```
With the server running (python app.py):

1. Input card smoke test:
   - Open http://127.0.0.1:5001. The input form and the empty-state
     placeholder should render. No commit cards, no repo-context card.

2. Happy path (specific commit):
   - Enter any public repo URL (e.g. https://github.com/pallets/flask).
   - Paste a short SHA from that repo's recent history.
   - Click Analyze. Spinner shows for 10–60 seconds on the first call
     (cold cache fetches README + runs Sonnet summarize + runs Opus analysis).
   - Result card appears: SHA + author + date header; clicking collapses/expands
     the body. The five sections render with a Low/Medium/High/Critical badge.

3. Cache check:
   - Analyze a second commit from the same repo. Server log should now show
     "repo context: hit (owner/repo)" and the call should be materially
     faster (10–25s vs the first call's 45–60s).

4. Dedupe + history cap:
   - Analyze six distinct commits from the same repo one at a time. The
     output window should retain at most 5 commit cards — oldest falls off
     the bottom as newest is prepended.
   - Re-analyze one of the commits still in the window; its card should be
     replaced in place, not duplicated.

5. Clear:
   - Click Clear. All cards are removed; empty-state returns.

6. Toggle check (INCLUDE_REPO_CONTEXT_IN_OUTPUT):
   - Edit commitlens/config.py → set to True. Restart the server.
     Run an analysis. A #repo-context-card should appear at the top of the
     output window with the Sonnet-generated summary. Flip back to False
     and restart: the card no longer appears.

7. Toggle check (INCLUDE_API_DETAILS):
   - Set to True. Restart. Analyze a commit that clearly touches an API
     endpoint. Output should now mention HTTP methods / endpoints in
     impacted_areas or qa_summary. Flip back to False — they should vanish.

8. Graceful failure:
   - Invalid URL → "Invalid GitHub URL." error banner.
   - Non-existent SHA → "Repository or commit not found."
   - Rate-limit exhausted (60 unauthenticated requests/hour) → paste your
     token into .github_token and restart; the startup banner should now
     read "GitHub auth: enabled".
```

---

## Key design decisions (non-obvious)

1. **Why `claude -p` subprocess, not the Anthropic SDK**
   The app is explicitly designed for developers who already have Claude Code installed and logged in. Reusing that session removes the need to hand out API keys, manage `.env` files, or handle billing inside the app. Trade-off: the CLI is slower (per-invocation cold start) and less flexible (no streaming in this mode).

2. **Why the prompt lives in `system_prompt.md` and not in code**
   The QA analyst persona evolves faster than the code. Keeping it as a Markdown file means prompt tweaks are one-line diffs that don't require a Python change, and the file is passed to `claude` via `--system-prompt-file` so Windows encoding quirks can't corrupt it.

3. **Why an app factory and blueprint for such a small app**
   Two reasons: (a) routes.py can be imported by tests without starting a server; (b) it makes adding a second blueprint (e.g. an admin page, a cache-stats endpoint) a non-event.

4. **Why `urllib` instead of `requests`**
   The only thing the app does with HTTP is two GitHub endpoints and one diff fetch. Standard library is enough and keeps `requirements.txt` to a single line.

5. **Why a module-level TTL cache instead of Redis**
   The cache is a 1-hour per-repo summary — at the app's expected scale (single developer, dev-only use), an in-memory dict is sufficient. The cache lives behind a `TTLCache` class so swapping in a real backend later is a one-file change.

6. **Why the frontend has no framework**
   Single page, one form, ≤5 collapsible cards, no state to speak of. A framework would be more code than the features warrant. Vanilla JS with a couple of render helpers is less than 300 lines and has no build step.

---

## Known gotchas (save yourself an hour)

- **Always use `--system-prompt-file`, never `--system-prompt` for non-ASCII prompt content on Windows.** See the detailed rationale in Phase 4 and the `commitlens/claude.py` docstring. This has bitten the project once; do not let it bite again.

- **`python app.py` with `debug=False` caches Jinja templates.** If you edit `templates/index.html`, restart the server. Edits to `system_prompt.md` do NOT require a restart (it's re-read every request via `--system-prompt-file`). Edits to `static/app.css` or `static/app.js` do NOT require a restart (Flask serves them fresh), but browser caches may interfere — hard-refresh the page.

- **GitHub's unauthenticated rate limit is 60 requests/hour per IP.** The analysis of one commit makes ~3 GitHub API calls (commit metadata + repo metadata + README), plus one per commit in last-n mode. Exhaust that and every subsequent analyze call returns "GitHub API rate limit reached." Fix: drop a token in `.github_token` (line 1 = the token) and restart.

- **The six-field schema is a contract.** `ANALYSIS_SCHEMA` (config.py), the prompt rules (`system_prompt.md`), and the frontend's `renderCommitCard` all reference the same keys. Renaming one requires editing all three. If you add a field, prefer appending rather than replacing, so older cached analyses in unconstrained callers don't break.

- **`.github_token` must be in `.gitignore`.** Verify before your first commit.

---

## Reference: current live layout

This playbook reproduces the layout currently in the repository. For the actual, live source of truth for each file, see the checked-in versions — especially `commitlens/analysis.py` and `commitlens/claude.py` for the subprocess plumbing, and [`system_prompt.md`](./system_prompt.md) for the QA analyst prompt.
