import {
  bindDataset,
  emptyState,
  escapeAttribute,
  escapeHtml,
  formatBytes,
  formatTime,
  statusPill,
} from "./utils.js";
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

export function renderSubscriptions(panel, subscriptions, filters, actions) {
  renderSubscriptionCards(panel, subscriptions, filters, actions);
}

export function renderAccounts(panel, accounts) {
  if (!accounts.length) {
    panel.innerHTML = emptyState("暂无登录账号");
    return;
  }
  panel.innerHTML = `<div class="cards">${accounts.map(accountCard).join("")}</div>`;
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

export function renderDiagnostics(panel, diagnostics, subscriptions, actions) {
  const targets = Array.from(new Set(subscriptions.map((sub) => sub.target_id))).filter(Boolean);
  panel.innerHTML = `
    <section class="action-panel">
      <div>
        <h2>手动直播检查</h2>
        <p>会向选中的会话推送当前正在直播的启用订阅。</p>
      </div>
      <div class="target-actions">
        <select id="manualTargetSelect" aria-label="目标会话">
          ${targets.map((target) => `<option value="${escapeAttribute(target)}">${escapeHtml(target)}</option>`).join("")}
        </select>
        <button class="ghost-button" id="manualLiveCheckButton" type="button" ${targets.length ? "" : "disabled"}>执行</button>
      </div>
    </section>
    <section class="diagnostic-grid">
      ${diagnosticItem("检查间隔", `${diagnostics.check_interval || "-"} 秒`)}
      ${diagnosticItem("渲染类型", diagnostics.render_type || "-")}
      ${diagnosticItem("链接解析", diagnostics.enable_link_parser ? "启用" : "停用")}
      ${diagnosticItem("AI 工具", diagnostics.enable_ai_tools ? "启用" : "停用")}
      ${diagnosticItem("Agent 入口", diagnostics.enable_ai_agent_entry ? "启用" : "停用")}
      ${diagnosticItem("会话数", diagnostics.targets || 0)}
    </section>
  `;
  panel.querySelector("#manualLiveCheckButton").addEventListener("click", () => {
    actions.onManualLive(panel.querySelector("#manualTargetSelect").value);
  });
}

export function renderTemplates(panel, previews, selectedPreview, actions) {
  panel.innerHTML = `
    <section class="template-actions">
      <button class="ghost-button" id="generateTemplatesButton" type="button">重新生成预览</button>
    </section>
    <section class="template-layout">
      <div class="preview-list">${previews.map(previewRow).join("") || emptyState("暂无模板预览")}</div>
      <div class="preview-viewer">
        ${selectedPreview ? previewImage(selectedPreview) : emptyState("选择一个预览文件")}
      </div>
    </section>
  `;
  bindDataset(panel, "[data-preview]", actions.onPreview);
  panel.querySelector("#generateTemplatesButton").addEventListener("click", actions.onGenerate);
}

export function showLoading(metrics) {
  metrics.innerHTML = "";
  for (const id of ["overviewPanel", "subscriptionsPanel", "accountsPanel", "pendingPanel", "diagnosticsPanel", "templatesPanel"]) {
    document.getElementById(id).innerHTML = emptyState("加载中");
  }
}

export function renderEmptyError(metrics) {
  metrics.innerHTML = "";
  for (const id of ["overviewPanel", "subscriptionsPanel", "accountsPanel", "pendingPanel", "diagnosticsPanel", "templatesPanel"]) {
    document.getElementById(id).innerHTML = emptyState("加载失败");
  }
}

function accountCard(account) {
  return `
    <article class="account-card">
      <img src="${escapeAttribute(account.face || "")}" alt="" />
      <div>
        <h2>${escapeHtml(account.name || "Bilibili 账号")}</h2>
        <p class="mono">UID ${escapeHtml(account.uid || "-")}</p>
      </div>
      ${statusPill(account.valid ? "有效" : "失效", account.valid)}
    </article>
  `;
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

function diagnosticItem(label, value) {
  return `<article class="diagnostic-item"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`;
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
