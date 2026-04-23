# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

CommitLens is a single-file Flask app (`app.py` + `templates/index.html`) that analyzes GitHub commits for QA risk. It shells out to the `claude` CLI in non-interactive mode (`claude -p`) rather than calling the Anthropic API directly, so it uses the developer's existing Claude Code session for auth — there is deliberately no `ANTHROPIC_API_KEY` handling anywhere in the codebase.

## Commands

- Install deps: `pip install -r requirements.txt` — only dependency is `flask`.
- Run: `python app.py` — serves on http://127.0.0.1:5001.
- No tests, no linter, no build step.
- Flask runs with `debug=False`, so Jinja caches templates. **Restart the server after editing `templates/index.html`** or changes won't appear.

## Architecture

Request flow for `POST /analyze`:

1. Browser posts `{repo_url, mode, sha|count}` to Flask.
2. `parse_repo_url` extracts `(owner, repo)`; commits are fetched via GitHub's **unauthenticated** public API — metadata with `Accept: application/vnd.github+json`, full diff with `Accept: application/vnd.github.diff`. Rate limits bite fast here.
3. For each commit, `analyze_with_claude` spawns `claude -p` as a subprocess with `--json-schema` and `--system-prompt-file`. Commit metadata + diff go in via stdin; structured JSON comes back on stdout inside an envelope whose `structured_output` key is the payload we return.
4. Frontend prepends new commit cards to the output window, dedupes by short SHA, and trims to 5 cards total. Clear button wipes all.

## The system prompt contract

`system_prompt.md` is the source of truth for the QA analyst persona, output shape, length caps (qa_summary ≤~60 words, risk_reasoning one sentence ≤25 words, test scenarios in `action → outcome` form ≤15 words), and the strict exclude list (no file paths, concurrency, performance, test infrastructure, CSS, security — unless the commit is explicitly about those).

`ANALYSIS_SCHEMA` in `app.py` must stay in sync with it: six required fields — `qa_summary`, `risk_level`, `risk_reasoning`, `impacted_areas`, `areas_needing_testing`, `test_scenarios`. The frontend (`renderCommitCard`) reads those exact keys. Changing any field name means editing three places: the schema in `app.py`, the prompt rules in `system_prompt.md`, and the template's JS.

## `INCLUDE_API_DETAILS` toggle

`app.py` line 12: `INCLUDE_API_DETAILS = False`. When `False`, `NO_API_APPEND` (an ASCII-only string) is appended to the system prompt via `--append-system-prompt` at each invocation, banning HTTP methods, endpoints, status codes, and request/response JSON shapes from the output. Flip to `True` to let API-level detail back in. The base prompt itself already prioritizes user-facing framing; the override is an extra guardrail.

## Windows gotcha — always use `--system-prompt-file`, never `--system-prompt`

On Windows, `shutil.which("claude")` resolves to `claude.CMD`, a batch wrapper. When Python's subprocess passes a long argv string to a `.CMD`, Windows transcodes each argument from Unicode to the console codepage (cp1252 in this locale). `system_prompt.md` contains characters outside cp1252 — `≤`, `→`, em dashes, curly quotes — which silently get replaced, corrupting the prompt before it reaches Claude. The symptom is Claude ignoring all the rules and producing generic output.

Passing the prompt path via `--system-prompt-file` sidesteps this: the path is ASCII, and `claude` reads the file as UTF-8 itself. `--append-system-prompt NO_API_APPEND` is fine *only* because that string is pure ASCII. **Any new runtime-constructed prompt content that may contain non-ASCII characters must be written to a file and passed with the `-file` variant, not inlined as an argv string.**

## Playbook doc

`UTILITY_INSTRUCTIONS.md` is the phased build record (Phases 1–8). Phases 1–7 describe the original greenfield browser-only build; Phase 8 documents the output-history UI behavior. The Flask refactor (`refactor: replace browser API calls with Flask backend using Claude Code CLI`), the externalized system prompt, and the `INCLUDE_API_DETAILS` toggle live in code and commit history but are not in the playbook.
