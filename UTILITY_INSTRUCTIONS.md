# Project Build Instructions
## QA Commit Analyzer Utility

**Prerequisites:**
- A GitHub repo named `qa-utility` created and cloned locally
- A valid Anthropic API key
- Run `claude` from the repo root before starting

---

## Project Structure

```
qa-utility/
├── index.html       # Main UI — single page app
├── config.js        # API key config (git-ignored)
├── config.sample.js # Safe template to commit
├── .gitignore       # Ensures config.js is never pushed
└── README.md        # Setup and usage instructions
```

---

## Phase 1: Project Setup

```
Create the folder structure and placeholder files for the QA utility project:

qa-utility/
├── index.html
├── config.js
├── config.sample.js
├── .gitignore
└── README.md

Do not implement any features yet. Only create empty placeholder files.
Do not commit yet.
```

---

## Phase 2: Commit 1 — Config & Gitignore

```
Implement the following for Commit 1:

1. In .gitignore: add config.js so the API key is never committed.

2. In config.sample.js: safe template showing structure without real key:
   const CONFIG = {
     ANTHROPIC_API_KEY: "your-api-key-here"
   };

3. In config.js: same structure as config.sample.js but with a placeholder 
   value. User will replace this with their real API key locally.

4. In README.md: setup and usage instructions covering:
   - Clone the repo
   - Copy config.sample.js to config.js
   - Add real Anthropic API key to config.js
   - Open index.html in a browser
   - How to use the utility (repo URL, commit SHA or last N commits)
   - Security note: config.js is git-ignored and never pushed

5. Commit with message: "chore: add config setup and gitignore"

Do not push yet.
```

---

## Phase 3: Commit 2 — Core UI

```
Implement the following for Commit 2:

1. In index.html: build a single-page utility with the following UI sections:

   HEADER:
   - Title: "QA Commit Analyzer"
   - Subtitle: "Analyze commits and generate QA insights instantly"

   INPUT SECTION:
   - Text input: GitHub repo URL (e.g. https://github.com/user/repo)
   - Radio toggle: "Specific Commit" or "Last N Commits"
   - If Specific Commit: text input for commit SHA
   - If Last N Commits: number input (1-10)
   - Analyze button

   RESULTS SECTION (hidden until analysis runs):
   - Commit metadata card: SHA, author, date, message
   - QA Summary (plain text)
   - Risk Level badge: color coded (Low=green, Medium=orange, 
     High=red, Critical=darkred)
   - Impacted Functional Areas (bulleted list)
   - Areas Needing Testing (bulleted list)
   - Test Scenario Suggestions (numbered list)

   FOOTER:
   - "Powered by Claude" note

2. Styling (embedded in index.html inside <style> tag):
   - Clean, minimal, professional
   - Card-based layout for results
   - Clear visual separation between sections
   - Responsive — works at different browser widths
   - No external CSS frameworks

3. Commit with message: "feat: add core UI layout and styling"

Do not push yet.
```

---

## Phase 4: Commit 3 — GitHub API Integration

```
Implement the following for Commit 3:

1. In index.html, inside <script> tag, add GitHub API integration:

   parseRepoUrl(url):
   - Extract owner and repo name from GitHub URL
   - Support formats: 
     https://github.com/owner/repo
     https://github.com/owner/repo.git

   fetchCommit(owner, repo, sha):
   - Call: GET https://api.github.com/repos/{owner}/{repo}/commits/{sha}
   - Return: { sha, message, author, date, files, diff }

   fetchLastNCommits(owner, repo, count):
   - Call: GET https://api.github.com/repos/{owner}/{repo}/commits?per_page={count}
   - For each commit, fetch full details including files changed
   - Return array of commit objects

   fetchPatch(owner, repo, sha):
   - Call: GET https://api.github.com/repos/{owner}/{repo}/commits/{sha}
     with Accept: application/vnd.github.diff header
   - Return raw diff text

2. Error handling:
   - Repo not found: show "Repository not found. Check the URL."
   - Rate limited: show "GitHub API rate limit reached. Try again later."
   - Invalid SHA: show "Commit not found. Check the SHA."
   - Network error: show "Network error. Check your connection."

3. Commit with message: "feat: add GitHub API integration"

Do not push yet.
```

---

## Phase 5: Commit 4 — Claude API Integration & QA Analysis

```
Implement the following for Commit 4:

1. In index.html, inside <script> tag, add Claude API integration:

   analyzeCommit(commitData):
   - Load API key from CONFIG.ANTHROPIC_API_KEY (from config.js)
   - Call Anthropic API: POST https://api.anthropic.com/v1/messages
   - Headers:
       Content-Type: application/json
       x-api-key: CONFIG.ANTHROPIC_API_KEY
       anthropic-version: 2023-06-01
       anthropic-dangerous-direct-browser-access: true
   - Model: claude-sonnet-4-20250514
   - max_tokens: 2000
   - Send this system prompt:
       "You are a Senior SDET. Analyze the provided git commit and return 
       a JSON object only — no markdown, no explanation, just raw JSON.
       
       Return exactly this structure:
       {
         "qa_summary": "plain text summary of what changed from a QA perspective",
         "risk_level": "Low | Medium | High | Critical",
         "risk_reasoning": "one sentence explaining the risk rating",
         "impacted_areas": ["area1", "area2"],
         "areas_needing_testing": ["area1", "area2"],
         "test_scenarios": [
           "Scenario description with input and expected result",
           ...
         ]
       }
       
       No BDD. No Given/When/Then. Plain language only."
   
   - Send user message containing:
       Commit SHA: {sha}
       Author: {author}
       Date: {date}
       Message: {message}
       
       Diff:
       {raw diff text}

2. parseAnalysis(response):
   - Parse JSON from Claude response
   - Map fields to UI sections
   - Handle parse errors gracefully

3. Wire up Analyze button:
   - On click: validate inputs → fetch commit(s) from GitHub → 
     send to Claude → render results
   - Show loading spinner while waiting
   - For multiple commits: analyze each separately and display 
     results in collapsible cards per commit

4. Commit with message: "feat: add Claude API integration and QA analysis"

Do not push yet.
```

---

## Phase 6: Commit 5 — Polish & Error Handling

```
Implement the following for Commit 5:

1. Loading states:
   - Spinner shown while GitHub API is fetching
   - "Analyzing with Claude..." message while Claude API is running
   - Disable Analyze button during processing

2. Empty state:
   - Before any analysis: show a simple placeholder message 
     "Enter a GitHub repo URL and commit details to get started"

3. Results persistence:
   - Last analysis result stays visible until a new analysis runs

4. Copy button:
   - Add a "Copy Report" button that copies the full analysis 
     as plain text to clipboard

5. Clear button:
   - Resets all inputs and hides results section

6. Commit with message: "feat: add polish, loading states and copy report"

Do not push yet.
```

---

## Phase 7: Push All Commits

```
Push all commits to origin main and confirm with git log --oneline.
```

---

## Phase 8: Output History (max 5)

```
Update the web UI so the output window preserves prior analyses instead of
overwriting them on every run:

1. On each successful analysis, prepend the new commit card(s) to the top of
   the results section instead of replacing the section's contents.

2. If the user re-analyzes a commit that is already in the output, the old
   card for that commit is removed before the new one is added, so each
   commit appears at most once.

3. Cap the output at 5 commit cards total. After prepending, trim older cards
   from the bottom so at most 5 remain.

4. Insert the loading spinner and any error banner at the top of the results
   section without clearing existing cards.

5. The Clear button continues to wipe all cards and return to the empty state.
```
