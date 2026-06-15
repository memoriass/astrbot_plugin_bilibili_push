import {
  emptyState,
  escapeHtml,
  formatTargetId,
  formatTime,
} from "./utils.js";
import { renderAccountManager } from "./accounts.js";
import { pendingCandidateText, pendingSummary, pendingTitle } from "./pending_text.js";
import { renderSubscriptionCards } from "./subscriptions.js";

export function renderMetrics(container, diagnostics) {
  const items = [
    ["总订阅", diagnostics.subscriptions || 0],
    ["启用", diagnostics.enabled_subscriptions || 0],
    ["动态", diagnostics.dynamic_subscriptions || 0],
    ["直播", diagnostics.live_subscriptions || 0],
    ["账号", `${diagnostics.valid_accounts || 0}/${diagnostics.accounts || 0}`],
    ["待处理", diagnostics.pending_tasks || 0],
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
  document.getElementById("metrics").hidden = activeTab !== "overview";
  document.getElementById("subscriptionToolbar").hidden = activeTab !== "subscriptions";
}

export function renderSubscriptions(
  panel,
  subscriptions,
  filters,
  actions,
  editor,
  deleteConfirm,
  pagination,
) {
  renderSubscriptionCards(
    panel,
    subscriptions,
    filters,
    actions,
    editor,
    deleteConfirm,
    pagination,
  );
}

export function renderAccounts(panel, accounts, actions, editor, deleteConfirm) {
  renderAccountManager(panel, accounts, actions, editor, deleteConfirm);
}

export function renderPending(panel, tasks, actions) {
  if (!tasks.length) {
    panel.innerHTML = emptyState("暂无待处理事项");
    return;
  }
  panel.innerHTML = `
    <div class="pending-actions">
      <button class="danger-button" id="clearPendingButton" type="button">清空待处理</button>
    </div>
    <div class="cards">${tasks.map(pendingCard).join("")}</div>
  `;
  panel.querySelector("#clearPendingButton").addEventListener("click", actions.onClear);
}

export function showLoading(metrics) {
  metrics.innerHTML = "";
  for (const id of ["overviewPanel", "subscriptionsPanel", "accountsPanel", "pendingPanel"]) {
    document.getElementById(id).innerHTML = emptyState("加载中");
  }
}

export function renderEmptyError(metrics) {
  metrics.innerHTML = "";
  for (const id of ["overviewPanel", "subscriptionsPanel", "accountsPanel", "pendingPanel"]) {
    document.getElementById(id).innerHTML = emptyState("加载失败");
  }
}

function pendingCard(task) {
  const origin = formatTargetId(task.origin) || "未知来源";
  return `
    <article class="pending-card">
      <div>
        <h2>${escapeHtml(pendingTitle(task))}</h2>
        <p>${escapeHtml(pendingSummary(task))}</p>
      </div>
      <dl>
        <div><dt>来源</dt><dd>${escapeHtml(origin)}</dd></div>
        <div><dt>候选</dt><dd>${escapeHtml(pendingCandidateText(task))}</dd></div>
        <div><dt>过期</dt><dd>${escapeHtml(formatTime(task.expires_at))}</dd></div>
      </dl>
    </article>
  `;
}
