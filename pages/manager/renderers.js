import {
  bindDataset,
  emptyState,
  escapeAttribute,
  escapeHtml,
  formatBytes,
  formatTime,
} from "./utils.js";
import { renderAccountManager } from "./accounts.js";
import { renderSubscriptionCards } from "./subscriptions.js";

export function renderMetrics(container, diagnostics) {
  const items = [
    ["总订阅", diagnostics.subscriptions || 0],
    ["启用", diagnostics.enabled_subscriptions || 0],
    ["动态", diagnostics.dynamic_subscriptions || 0],
    ["直播", diagnostics.live_subscriptions || 0],
    ["账号", `${diagnostics.valid_accounts || 0}/${diagnostics.accounts || 0}`],
    ["Pending", diagnostics.pending_tasks || 0],
  ];
  container.innerHTML = items
    .map(([label, value]) => `
      <article class="metric">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </article>
    `)
    .join("");
}

export function renderTabs(activeTab) {
  document.querySelectorAll(".tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === activeTab);
  });
  document.querySelectorAll(".panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `${activeTab}Panel`);
  });
  document.getElementById("subscriptionToolbar").hidden = activeTab !== "subscriptions";
}

export function renderSubscriptions(panel, subscriptions, filters, actions, editor) {
  renderSubscriptionCards(panel, subscriptions, filters, actions, editor);
}

export function renderAccounts(panel, accounts, actions, editor) {
  renderAccountManager(panel, accounts, actions, editor);
}

export function renderPending(panel, tasks, actions) {
  if (!tasks.length) {
    panel.innerHTML = emptyState("暂无 pending 任务");
    return;
  }
  panel.innerHTML = `
    <div class="pending-actions">
      <button class="danger-button" id="clearPendingButton" type="button">清空 Pending</button>
    </div>
    <div class="cards">${tasks.map(pendingCard).join("")}</div>
  `;
  panel.querySelector("#clearPendingButton").addEventListener("click", actions.onClear);
}

export function renderTemplates(panel, previews, selectedPreview, actions) {
  panel.innerHTML = `
    <section class="template-actions">
      <div>
        <h2>模板预览</h2>
        <p>使用当前模板和样例 Bilibili 数据生成本地 PNG，选择条目后在右侧查看。</p>
      </div>
      <div class="template-controls">
        <input id="templateSeedInput" type="number" inputmode="numeric" value="${escapeAttribute(actions.seed)}" aria-label="随机种子" />
        <button class="ghost-button" id="refreshTemplatesButton" type="button">刷新列表</button>
        <button class="ghost-button" id="generateTemplatesButton" type="button">生成预览</button>
      </div>
    </section>
    <section class="template-layout">
      <div class="preview-list">${previews.map(previewRow).join("") || emptyState("暂无模板预览")}</div>
      <div class="preview-viewer">
        ${selectedPreview ? previewImage(selectedPreview) : emptyState("选择一个预览文件")}
      </div>
    </section>
  `;
  bindDataset(panel, "[data-preview]", actions.onPreview);
  panel.querySelector("#refreshTemplatesButton").addEventListener("click", actions.onRefresh);
  panel.querySelector("#generateTemplatesButton").addEventListener("click", actions.onGenerate);
}

export function showLoading(metrics) {
  metrics.innerHTML = "";
  for (const id of ["overviewPanel", "subscriptionsPanel", "accountsPanel", "pendingPanel", "templatesPanel"]) {
    document.getElementById(id).innerHTML = emptyState("加载中");
  }
}

export function renderEmptyError(metrics) {
  metrics.innerHTML = "";
  for (const id of ["overviewPanel", "subscriptionsPanel", "accountsPanel", "pendingPanel", "templatesPanel"]) {
    document.getElementById(id).innerHTML = emptyState("加载失败");
  }
}

function pendingCard(task) {
  return `
    <article class="pending-card">
      <div><h2>${escapeHtml(task.task_id)}</h2><p>${escapeHtml(task.kind || task.workflow || "-")}</p></div>
      <dl>
        <div><dt>来源</dt><dd class="mono">${escapeHtml(task.origin || "-")}</dd></div>
        <div><dt>候选</dt><dd>${escapeHtml(task.candidate_count || 0)}</dd></div>
        <div><dt>过期</dt><dd>${escapeHtml(formatTime(task.expires_at))}</dd></div>
      </dl>
    </article>
  `;
}

function previewRow(preview) {
  return `
    <article class="preview-card">
      <div>
        <h2>${escapeHtml(preview.label || preview.name)}</h2>
        <p>${escapeHtml(preview.name)} · ${escapeHtml(formatBytes(preview.size))}</p>
      </div>
      <button class="ghost-button" type="button" data-preview="${escapeAttribute(preview.name)}">查看</button>
    </article>
  `;
}

function previewImage(preview) {
  return `
    <figure class="preview-image">
      <img src="${escapeAttribute(preview.data_url)}" alt="${escapeAttribute(preview.label || preview.name)}" />
      <figcaption>${escapeHtml(preview.label || preview.name)} · ${escapeHtml(formatBytes(preview.size))}</figcaption>
    </figure>
  `;
}
