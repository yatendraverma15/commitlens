# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

CommitLens is a Flask web app that analyzes GitHub commits for QA risk. It shells out to the `claude` CLI in non-interactive mode (`claude -p`) rather than calling the Anthropic API directly, so it uses the developer's existing Claude Code session for auth — there is deliberately no `ANTHROPIC_API_KEY` handling anywhere in the codebase.

## Commands

- Install deps: `pip install -r requirements.txt` — only dependency is `flask`.
- Run: `python app.py` — serves on http://127.0.0.1:5001.
- No tests, no linter, no build step.
- Flask runs with `debug=False`, so Jinja caches templates. **Restart the server after editing `templates/index.html`.** Edits to `system_prompt.md`, `static/app.css`, and `static/app.js` do NOT require a restart — the prompt file is re-read every `/analyze` call, and static assets are served fresh from disk (hard-refresh the browser if you don't see CSS/JS changes).

## Layout

```
app.py                          # thin entrypoint: create_app() and app.run
commitlens/                     # package
├── __init__.py                 # create_app() factory + logging setup
├── config.py                   # constants: CLAUDE_BIN, GITHUB_TOKEN, PROMPT_PATH, toggles, ANALYSIS_SCHEMA, NO_API_APPEND, REPO_SUMMARY_SYSTEM_PROMPT
├── errors.py                   # APIError + register_error_handlers()
├── models.py                   # @dataclass(frozen=True) Commit
├── cache.py                    # TTLCache[T] helper
├── github.py                   # parse_repo_url, fetch_commit, fetch_last_n, fetch_diff, fetch_repo_meta, fetch_readme
├── claude.py                   # run_text_summary, run_structured_analysis (subprocess wrappers)
├── analysis.py                 # summarize_repo (cached), analyze_commit
└── routes.py                   # Blueprint("main"): GET /, POST /analyze
static/                         # app.css, app.js (served by Flask at /static/...)
templates/index.html            # skeleton; references url_for('static', ...)
system_prompt.md                # externalized QA analyst prompt (loaded via --system-prompt-file)
UTILITY_INSTRUCTIONS.md         # phased build playbook — hand to an assistant to recreate the app from scratch
```

## Architecture

Request flow for `POST /analyze` (handled by `routes.py:analyze`):

1. Browser posts `{repo_url, mode, sha|count}` to Flask.
2. `parse_repo_url` extracts `(owner, repo)`; commits are fetched via GitHub's public API (authenticated if `.github_token` or `GITHUB_TOKEN` is set, else unauthenticated — rate limits bite fast at 60/hr). Metadata uses `Accept: application/vnd.github+json`; full diff uses `Accept: application/vnd.github.diff`.
3. `analysis.summarize_repo(owner, repo)` runs **once per request, cached per repo for 1 hour**: it fetches repo metadata + README and invokes `claude -p --model sonnet` to produce a 4–8 sentence user-facing summary. Empty summary if README is missing or the Sonnet call fails (falls back to `meta.description`).
4. For each commit, `analysis.analyze_commit(commit, diff, repo_context)` builds a user message — `## Repository Context` block (if any) + `## Commit` block — and invokes `claude -p --model opus` with `--json-schema` and `--system-prompt-file`. Structured JSON comes back on stdout inside an envelope whose `structured_output` key is the payload returned to the frontend.
5. Frontend (`static/app.js`) prepends new commit cards to the output window, dedupes by short SHA, and trims to 5 cards total. Clear button wipes all. If the response includes a top-level `repo_context` (only when the toggle is on), `#repo-context-card` renders above the commit cards.

## The system prompt contract

`system_prompt.md` is the source of truth for the QA analyst persona, output shape, length caps (qa_summary ≤~60 words, risk_reasoning one sentence ≤25 words, test_scenarios in `action → outcome` form ≤15 words), the strict exclude list (no file paths, concurrency, performance, test infrastructure, CSS, security — unless the commit is explicitly about those), **Pre-analysis framing** (use injected Repository Context block when present; infer from diff signals otherwise), and **Tool and framework awareness** (recognize Ranorex, Selenium, pytest, React, Django, Docker, etc., and frame test_scenarios in tool-appropriate language — tools are explicitly exempted from the "no code-layer references" rule).

`ANALYSIS_SCHEMA` in `commitlens/config.py` must stay in sync with it: six required fields — `qa_summary`, `risk_level`, `risk_reasoning`, `impacted_areas`, `areas_needing_testing`, `test_scenarios`. The frontend (`static/app.js: renderCommitCard`) reads those exact keys. Changing any field name means editing three places: the schema in `commitlens/config.py`, the prompt rules in `system_prompt.md`, and `static/app.js`.

## Runtime toggles (both in `commitlens/config.py`)

### `INCLUDE_API_DETAILS` (default `False`)

When `False`, `NO_API_APPEND` (an ASCII-only string) is passed to each per-commit `claude` invocation via `--append-system-prompt`. It bans HTTP methods, endpoints, URLs, status codes, and request/response JSON shapes from the output and forces user-facing wording. Flip to `True` to let API-level detail back in.

### `INCLUDE_REPO_CONTEXT_IN_OUTPUT` (default `False`)

When `True`, `routes.analyze` includes the cached repo-context summary in the `/analyze` response as a top-level `repo_context` key. The frontend's `renderRepoContext()` renders it as a card above the commit cards. Off by default because the summary is intended as internal framing for the model, not user-visible output.

Both toggles take effect on server restart.

## Windows gotcha — always use `--system-prompt-file`, never `--system-prompt`

On Windows, `shutil.which("claude")` resolves to `claude.CMD`, a batch wrapper. When Python's subprocess passes a long argv string to a `.CMD`, Windows transcodes each argument from Unicode to the console codepage (cp1252 in this locale). `system_prompt.md` contains characters outside cp1252 — `≤`, `→`, em dashes, curly quotes — which silently get replaced, corrupting the prompt before it reaches Claude. The symptom is Claude ignoring all the rules and producing generic output.

`commitlens/claude.py:run_structured_analysis` sidesteps this by passing the prompt file path via `--system-prompt-file`: the path is ASCII, and `claude` reads the file as UTF-8 itself. `--append-system-prompt NO_API_APPEND` is fine *only* because that string is pure ASCII. **Any new runtime-constructed prompt content that may contain non-ASCII characters must be written to a file and passed with the `-file` variant, not inlined as an argv string.**

`run_text_summary` (used for the repo-context summarization) is intentionally allowed to use `--system-prompt` because `REPO_SUMMARY_SYSTEM_PROMPT` in `config.py` is pure ASCII. If that string is ever edited to include non-ASCII characters, it must also move to a file.

## Playbook doc

`UTILITY_INSTRUCTIONS.md` is a complete phased build prompt (11 phases) covering the current architecture: scaffold → package core → GitHub client → Claude subprocess wrapper → analysis orchestration → routes blueprint → frontend → entrypoint → the externalized system prompt → runtime toggles → end-to-end verification. Hand it to an assistant to rebuild the app from an empty directory.
