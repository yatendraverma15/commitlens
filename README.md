# CommitLens — QA Commit Analyzer

Analyze GitHub commits and generate instant QA insights. Powered by **Claude Code** (no API key required — uses your existing Claude Code / Team license).

## How it works

```
Browser UI  ──►  Flask backend  ──►  claude -p  ──►  QA Report
                       │
                       └──►  GitHub API (public repos)
```

The Flask backend calls the `claude` CLI in non-interactive mode, so your existing Claude Code session handles the authentication. No `ANTHROPIC_API_KEY` needed.

## Prerequisites

- Python 3.9+
- Claude Code installed and signed in (`claude` must be on your PATH)

## Setup

```bash
git clone https://github.com/yatendraverma15/commitlens.git
cd commitlens
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Then open **http://127.0.0.1:5001** in your browser.

## Usage

1. Paste a GitHub repository URL (e.g. `https://github.com/owner/repo`)
2. Choose analysis mode:
   - **Specific Commit** — enter a commit SHA (full or short)
   - **Last N Commits** — enter a number between 1 and 10
3. Click **Analyze**
4. Review the QA summary, risk level, impacted areas, and test scenarios
5. Use **Copy Report** to grab the analysis as plain text, or **Clear** to reset

Each commit takes ~5–10 seconds to analyze. For multiple commits, analysis runs sequentially.

## Security

No API keys, no stored credentials, no external config files. The app runs entirely on your local machine and talks to:
- **GitHub** (public API, read-only)
- **Claude Code CLI** (uses your signed-in session)
