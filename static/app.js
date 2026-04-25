// --- UI mode toggle ---
document.querySelectorAll('input[name="mode"]').forEach(radio => {
  radio.addEventListener("change", () => {
    const specific = radio.value === "specific";
    document.getElementById("sha-field").classList.toggle("hidden", !specific);
    document.getElementById("n-field").classList.toggle("hidden", specific);
  });
});

// --- Display helpers ---
const MAX_RESULTS = 5;

function setActionBar(visible) {
  document.getElementById("action-bar").style.display = visible ? "flex" : "none";
}

function showEmpty() {
  document.getElementById("empty-state").classList.remove("hidden");
  const sec = document.getElementById("results-section");
  sec.classList.add("hidden");
  sec.innerHTML = "";
  renderRepoContext("");
  setActionBar(false);
}

function renderRepoContext(ctx) {
  const card = document.getElementById("repo-context-card");
  const text = document.getElementById("repo-context-text");
  if (ctx) {
    text.textContent = ctx;
    card.classList.remove("hidden");
  } else {
    text.textContent = "";
    card.classList.add("hidden");
  }
}

function removeTransient() {
  const sec = document.getElementById("results-section");
  sec.querySelector(".spinner-wrap")?.remove();
  sec.querySelector(".error-msg")?.remove();
}

function showSpinner(msg) {
  document.getElementById("empty-state").classList.add("hidden");
  const sec = document.getElementById("results-section");
  sec.classList.remove("hidden");
  removeTransient();
  const el = document.createElement("div");
  el.className = "spinner-wrap";
  el.innerHTML = `<span class="spinner"></span>${escapeHtml(msg)}`;
  sec.insertBefore(el, sec.firstChild);
}

function showError(msg) {
  document.getElementById("empty-state").classList.add("hidden");
  const sec = document.getElementById("results-section");
  sec.classList.remove("hidden");
  removeTransient();
  const el = document.createElement("div");
  el.className = "error-msg";
  el.textContent = msg;
  sec.insertBefore(el, sec.firstChild);
}

function trimResults() {
  const sec = document.getElementById("results-section");
  const cards = sec.querySelectorAll(".commit-card");
  for (let i = MAX_RESULTS; i < cards.length; i++) cards[i].remove();
}

function riskClass(level) {
  return { Low: "risk-low", Medium: "risk-medium", High: "risk-high", Critical: "risk-critical" }[level] ?? "risk-medium";
}

function renderList(items, ordered) {
  const tag = ordered ? "ol" : "ul";
  const cls = ordered ? "numbered-list" : "bullet-list";
  if (!items || items.length === 0) return `<div style="color:#94a3b8;font-size:0.85rem;">None.</div>`;
  return `<${tag} class="${cls}">${items.map(i => `<li>${escapeHtml(i)}</li>`).join("")}</${tag}>`;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function renderCommitCard(commit, analysis) {
  const shortSha = commit.sha.slice(0, 7);
  const risk = analysis.risk_level ?? "Medium";
  const copyIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;
  return `
    <div class="commit-card">
      <div class="commit-header" onclick="if (event.target.closest('.copy-commit-btn')) return; this.nextElementSibling.classList.toggle('hidden');">
        <span class="sha">${shortSha}</span>
        <span class="meta">${escapeHtml(commit.author)} &middot; ${new Date(commit.date).toLocaleDateString()}</span>
        <div class="commit-header-right">
          <button class="copy-commit-btn" type="button" title="Copy this commit's analysis" onclick="copyCommitCard(this)">
            ${copyIcon}<span>Copy</span>
          </button>
          <span class="toggle">&#9660;</span>
        </div>
      </div>
      <div class="commit-body">
        <div class="commit-msg">"${escapeHtml(commit.message)}"</div>

        <div>
          <div class="section-label">QA Summary</div>
          <div class="qa-summary">${escapeHtml(analysis.qa_summary ?? "—")}</div>
        </div>

        <div>
          <div class="section-label">Risk Level</div>
          <span class="risk-badge ${riskClass(risk)}">${risk}</span>
          <div class="risk-reasoning">${escapeHtml(analysis.risk_reasoning ?? "")}</div>
        </div>

        <div>
          <div class="section-label">Impacted Functional Areas</div>
          ${renderList(analysis.impacted_areas, false)}
        </div>

        <div>
          <div class="section-label">Areas Needing Testing</div>
          ${renderList(analysis.areas_needing_testing, false)}
        </div>

        <div>
          <div class="section-label">Test Scenario Suggestions</div>
          ${renderList(analysis.test_scenarios, true)}
        </div>
      </div>
    </div>`;
}

// --- Clear ---
document.getElementById("clear-btn").addEventListener("click", () => {
  document.getElementById("repo-url").value = "";
  document.getElementById("commit-sha").value = "";
  document.getElementById("commit-count").value = "5";
  document.querySelector('input[name="mode"][value="specific"]').checked = true;
  document.getElementById("sha-field").classList.remove("hidden");
  document.getElementById("n-field").classList.add("hidden");
  showEmpty();
});

// --- Per-commit copy ---
function copyCommitCard(btn) {
  const card = btn.closest(".commit-card");
  if (!card) return;
  const sha  = card.querySelector(".sha")?.textContent ?? "";
  const meta = card.querySelector(".meta")?.textContent ?? "";
  const msg  = card.querySelector(".commit-msg")?.textContent?.trim() ?? "";
  const body = card.querySelector(".commit-body");
  const lines = [`=== Commit ${sha} — ${meta} ===`, msg];
  body.querySelectorAll(".section-label").forEach(label => {
    lines.push(`\n${label.textContent}`);
    const next = label.nextElementSibling;
    if (next) lines.push(next.textContent.trim());
  });
  navigator.clipboard.writeText(lines.join("\n")).then(() => {
    const span = btn.querySelector("span");
    const orig = span.textContent;
    span.textContent = "Copied!";
    btn.classList.add("copied");
    setTimeout(() => { span.textContent = orig; btn.classList.remove("copied"); }, 2000);
  });
}

// --- Analyze button ---
document.getElementById("analyze-btn").addEventListener("click", async () => {
  const repoUrl = document.getElementById("repo-url").value.trim();
  const mode    = document.querySelector('input[name="mode"]:checked').value;
  const btn     = document.getElementById("analyze-btn");

  if (!repoUrl) { showError("Please enter a GitHub repository URL."); return; }

  let payload = { repo_url: repoUrl, mode };
  if (mode === "specific") {
    const sha = document.getElementById("commit-sha").value.trim();
    if (!sha) { showError("Please enter a commit SHA."); return; }
    payload.sha = sha;
  } else {
    payload.count = parseInt(document.getElementById("commit-count").value) || 5;
  }

  btn.disabled = true;
  showSpinner("Fetching commits and analyzing with Claude… this can take 10–60 seconds.");

  try {
    const res  = await fetch("/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (!res.ok) {
      showError(data.error ?? "Analysis failed.");
      return;
    }

    removeTransient();
    renderRepoContext(data.repo_context || "");

    const results = document.getElementById("results-section");
    document.getElementById("empty-state").classList.add("hidden");
    results.classList.remove("hidden");

    // Dedupe: if a new commit matches an existing card's SHA, drop the old card.
    const incomingShas = new Set(data.results.map(r => r.commit.sha.slice(0, 7)));
    results.querySelectorAll(".commit-card").forEach(card => {
      const sha = card.querySelector(".sha")?.textContent;
      if (sha && incomingShas.has(sha)) card.remove();
    });

    // Prepend newest-first so order within the batch is preserved.
    const tmp = document.createElement("div");
    tmp.innerHTML = data.results
      .map(({ commit, analysis }) => renderCommitCard(commit, analysis))
      .join("");
    Array.from(tmp.children).reverse().forEach(card => {
      results.insertBefore(card, results.firstChild);
    });

    trimResults();
    setActionBar(true);
  } catch (e) {
    showError("Could not reach the server. Is the Flask app running?");
  } finally {
    btn.disabled = false;
  }
});
