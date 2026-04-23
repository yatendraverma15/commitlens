# CommitLens — QA Commit Analyzer

Analyze GitHub commits and generate instant QA insights powered by Claude.

## Setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/yatendraverma15/commitlens.git
   cd commitlens
   ```

2. **Configure your API key**
   ```bash
   cp config.sample.js config.js
   ```
   Open `config.js` and replace `your-api-key-here` with your real Anthropic API key.

3. **Open the app**
   Open `index.html` directly in your browser — no server needed.

## Usage

1. Paste a GitHub repository URL (e.g. `https://github.com/owner/repo`)
2. Choose analysis mode:
   - **Specific Commit** — enter a commit SHA
   - **Last N Commits** — enter a number between 1 and 10
3. Click **Analyze**
4. Review the QA summary, risk level, impacted areas, and test scenarios

## Security

`config.js` is listed in `.gitignore` and will never be committed or pushed.
Your API key stays local to your machine.
