const state = {
  payload: null,
  history: null,
  apiAvailable: false,
  search: "",
  category: "",
  sort: "score",
  userState: { schema_version: 1, papers: {} },
};

const elements = {
  summary: document.querySelector("#summary"),
  paperList: document.querySelector("#paperList"),
  status: document.querySelector("#status"),
  searchInput: document.querySelector("#searchInput"),
  categoryFilter: document.querySelector("#categoryFilter"),
  sortSelect: document.querySelector("#sortSelect"),
  historySelect: document.querySelector("#historySelect"),
  refreshButton: document.querySelector("#refreshButton"),
  exportJson: document.querySelector("#exportJson"),
};

init();

async function init() {
  bindEvents();
  state.apiAvailable = await detectApi();
  await Promise.all([loadRecommendations(), loadHistory(), loadUserState()]);
  render();
}

function bindEvents() {
  elements.searchInput.addEventListener("input", (event) => {
    state.search = event.target.value.trim().toLowerCase();
    renderPapers();
  });

  elements.categoryFilter.addEventListener("change", (event) => {
    state.category = event.target.value;
    renderPapers();
  });

  elements.sortSelect.addEventListener("change", (event) => {
    state.sort = event.target.value;
    renderPapers();
  });

  elements.historySelect.addEventListener("change", async (event) => {
    const date = event.target.value;
    if (!date) return;
    await loadRecommendations(date);
    render();
  });

  elements.refreshButton.addEventListener("click", refreshRecommendations);

  elements.paperList.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-state-action]");
    if (!button) return;
    await togglePaperState(button.dataset.arxivId, button.dataset.stateAction);
  });
}

async function detectApi() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    return response.ok;
  } catch {
    return false;
  }
}

async function loadRecommendations(date = "") {
  setStatus("正在加载推荐数据...");
  const url = date
    ? state.apiAvailable
      ? `/api/recommendations/${date}`
      : `data/daily/${date}.json`
    : state.apiAvailable
      ? "/api/recommendations"
      : "data/recommendations.json";

  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.payload = await response.json();
    elements.exportJson.href = date ? `data/daily/${date}.json` : "data/recommendations.json";
    setStatus("");
  } catch (error) {
    state.payload = null;
    setStatus(`无法加载推荐数据：${error.message}`);
  }
}

async function loadHistory() {
  try {
    const url = state.apiAvailable ? "/api/history" : "data/history.json";
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.history = await response.json();
  } catch {
    state.history = { dates: [] };
  }
}

async function loadUserState() {
  if (!state.apiAvailable) {
    state.userState = readLocalState();
    return;
  }

  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.userState = await response.json();
  } catch {
    state.userState = readLocalState();
  }
}

async function togglePaperState(arxivId, field) {
  const current = getPaperState(arxivId);
  const nextValue = !current[field];
  state.userState.papers = state.userState.papers || {};
  state.userState.papers[arxivId] = { ...current, [field]: nextValue };

  if (state.apiAvailable) {
    try {
      const response = await fetch("/api/state", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ arxiv_id: arxivId, [field]: nextValue }),
      });
      if (response.ok) {
        state.userState = await response.json();
      }
    } catch {
      writeLocalState(state.userState);
    }
  } else {
    writeLocalState(state.userState);
  }

  renderPapers();
}

async function refreshRecommendations() {
  if (!state.apiAvailable) {
    setStatus("当前是静态部署模式，刷新推荐需要通过 GitHub Actions 或本地服务完成。");
    return;
  }

  elements.refreshButton.disabled = true;
  setStatus("正在刷新推荐，这可能需要几十秒...");
  try {
    const response = await fetch("/api/refresh", { method: "POST" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    await response.json();
    await Promise.all([loadRecommendations(), loadHistory()]);
    render();
    setStatus("推荐已刷新。");
  } catch (error) {
    setStatus(`刷新失败：${error.message}`);
  } finally {
    elements.refreshButton.disabled = false;
  }
}

function render() {
  renderHistory();
  renderSummary();
  renderCategories();
  renderPapers();
}

function renderHistory() {
  const dates = state.history?.dates || [];
  const currentDate = state.payload?.date || "";
  elements.historySelect.innerHTML = [
    `<option value="">最新推荐</option>`,
    ...dates.map((item) => {
      const selected = item.date === currentDate ? "selected" : "";
      return `<option value="${escapeHtml(item.date)}" ${selected}>${escapeHtml(item.date)} · ${item.selected} 篇</option>`;
    }),
  ].join("");
}

function renderSummary() {
  if (!state.payload) {
    elements.summary.innerHTML = "";
    return;
  }

  const { profile, stats, filters, generated_at } = state.payload;
  elements.summary.innerHTML = [
    stat("Profile", profile?.name || "N/A"),
    stat("推荐日期", state.payload.date || "N/A"),
    stat("选中 / 匹配", `${stats?.selected ?? 0} / ${stats?.matched ?? 0}`),
    stat("最低分", filters?.min_score ?? "N/A"),
    stat("生成时间", formatDateTime(generated_at)),
    stat("分类", (profile?.categories || []).join(", ") || "N/A"),
    stat("关键词", (profile?.keywords || []).slice(0, 4).join(", ") || "N/A"),
    stat("抓取数量", stats?.fetched ?? 0),
  ].join("");
}

function stat(label, value) {
  return `<div class="stat"><p class="stat-label">${escapeHtml(label)}</p><p class="stat-value">${escapeHtml(String(value))}</p></div>`;
}

function renderCategories() {
  const categories = new Set();
  for (const paper of state.payload?.papers || []) {
    for (const category of paper.categories || []) categories.add(category);
  }
  const options = [...categories].sort().map((category) => {
    const selected = state.category === category ? "selected" : "";
    return `<option value="${escapeHtml(category)}" ${selected}>${escapeHtml(category)}</option>`;
  });
  elements.categoryFilter.innerHTML = `<option value="">全部分类</option>${options.join("")}`;
}

function renderPapers() {
  if (!state.payload) {
    elements.paperList.innerHTML = `<div class="empty">还没有推荐数据。请先运行推荐任务。</div>`;
    return;
  }

  const papers = filterAndSort(state.payload.papers || []);
  if (papers.length === 0) {
    elements.paperList.innerHTML = `<div class="empty">当前筛选条件下没有论文。</div>`;
    return;
  }

  elements.paperList.innerHTML = papers.map(renderPaper).join("");
}

function filterAndSort(papers) {
  const filtered = papers.filter((paper) => {
    const text = [
      paper.title,
      paper.abstract,
      (paper.authors || []).join(" "),
      (paper.categories || []).join(" "),
      (paper.matched_keywords || []).join(" "),
    ].join(" ").toLowerCase();
    const matchesSearch = !state.search || text.includes(state.search);
    const matchesCategory = !state.category || (paper.categories || []).includes(state.category);
    return matchesSearch && matchesCategory;
  });

  return filtered.sort((a, b) => {
    if (state.sort === "updated") return new Date(b.updated) - new Date(a.updated);
    if (state.sort === "published") return new Date(b.published) - new Date(a.published);
    return (b.score || 0) - (a.score || 0);
  });
}

function renderPaper(paper) {
  const paperState = getPaperState(paper.arxiv_id);
  const categories = (paper.categories || []).map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("");
  const keywords = (paper.matched_keywords || []).map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("");
  const reasons = (paper.recommendation_reasons || []).map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("");
  const states = [
    paperState.favorite ? '<span class="chip">已收藏</span>' : "",
    paperState.read ? '<span class="chip">已读</span>' : "",
    paperState.ignored ? '<span class="chip">已忽略</span>' : "",
  ].join("");
  const downloadHref = state.apiAvailable
    ? `/api/download/${encodeURIComponent(paper.arxiv_id)}`
    : paper.pdf_url;

  return `
    <article class="paper ${paperState.ignored ? "is-ignored" : ""}">
      <div class="paper-head">
        <h2>${paper.rank}. ${escapeHtml(paper.title)}</h2>
        <div class="score">${Number(paper.score || 0).toFixed(1)}</div>
      </div>
      <p class="meta">
        ${escapeHtml((paper.authors || []).join(", ") || "N/A")}
        · 发布 ${formatDate(paper.published)}
        · 更新 ${formatDate(paper.updated)}
      </p>
      <div class="chips">${categories}</div>
      <div class="chips">${states}</div>
      <p class="abstract">${escapeHtml(paper.abstract || "")}</p>
      <div class="chips">${keywords || '<span class="chip">无关键词命中</span>'}</div>
      <div class="chips">${reasons}</div>
      <div class="paper-actions">
        <a class="button" href="${escapeAttr(paper.abs_url)}" target="_blank" rel="noreferrer">打开 arXiv</a>
        <a class="button secondary" href="${escapeAttr(downloadHref)}" target="_blank" rel="noreferrer" download>下载 PDF</a>
        <button class="secondary state-button" type="button" data-state-action="favorite" data-arxiv-id="${escapeAttr(paper.arxiv_id)}">${paperState.favorite ? "取消收藏" : "收藏"}</button>
        <button class="secondary state-button" type="button" data-state-action="read" data-arxiv-id="${escapeAttr(paper.arxiv_id)}">${paperState.read ? "标为未读" : "标为已读"}</button>
        <button class="secondary state-button" type="button" data-state-action="ignored" data-arxiv-id="${escapeAttr(paper.arxiv_id)}">${paperState.ignored ? "取消忽略" : "忽略"}</button>
      </div>
    </article>
  `;
}

function getPaperState(arxivId) {
  return state.userState?.papers?.[arxivId] || {};
}

function readLocalState() {
  try {
    return JSON.parse(localStorage.getItem("auto_arxiv_user_state") || '{"schema_version":1,"papers":{}}');
  } catch {
    return { schema_version: 1, papers: {} };
  }
}

function writeLocalState(value) {
  localStorage.setItem("auto_arxiv_user_state", JSON.stringify(value));
}

function setStatus(message) {
  elements.status.textContent = message;
}

function formatDate(value) {
  if (!value) return "N/A";
  return new Date(value).toISOString().slice(0, 10);
}

function formatDateTime(value) {
  if (!value) return "N/A";
  return new Date(value).toLocaleString();
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[char]);
}

function escapeAttr(value) {
  return escapeHtml(value || "");
}
