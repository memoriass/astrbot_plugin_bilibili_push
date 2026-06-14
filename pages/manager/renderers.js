import {
  emptyState,
  escapeAttribute,
  escapeHtml,
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

export function renderSubscriptions(panel, subscriptions, filters, actions, editor, deleteConfirm) {
  renderSubscriptionCards(panel, subscriptions, filters, actions, editor, deleteConfirm);
}

export function renderAccounts(panel, accounts, actions, editor, deleteConfirm) {
  renderAccountManager(panel, accounts, actions, editor, deleteConfirm);
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
