import {
  bindDataset,
  emptyState,
  escapeAttribute,
  escapeHtml,
  statusPill,
  typeBadge,
} from "./utils.js";

export function renderSubscriptionCards(panel, subscriptions, filters, actions) {
  const filtered = filterSubscriptions(subscriptions, filters);
  if (!filtered.length) {
    panel.innerHTML = emptyState("没有匹配的订阅");
    return;
  }

  const enabledCount = filtered.filter((sub) => sub.enabled).length;
  panel.innerHTML = `
    <section class="subscription-summary">
      <div>
        <h2>订阅卡片</h2>
        <p>当前匹配 ${escapeHtml(filtered.length)} 个订阅，启用 ${escapeHtml(enabledCount)} 个。</p>
      </div>
      <div class="subscription-summary-badges">
        ${summaryBadge("动态", filtered.filter((sub) => sub.sub_type === "dynamic").length)}
        ${summaryBadge("直播", filtered.filter((sub) => sub.sub_type === "live").length)}
      </div>
    </section>
    <section class="subscription-card-grid">
      ${filtered.map(subscriptionCard).join("")}
    </section>
  `;
  bindDataset(panel, "[data-toggle]", actions.onToggle);
  bindDataset(panel, "[data-delete]", actions.onDelete);
}

function filterSubscriptions(subscriptions, filters) {
  return subscriptions.filter((sub) => {
    const labels = [...(sub.categories || []), ...(sub.tags || [])].join(" ");
    const haystack = `${sub.uid} ${sub.username} ${sub.target_id} ${labels}`.toLowerCase();
    const typeMatched = filters.type === "all" || sub.sub_type === filters.type;
    return typeMatched && (!filters.query || haystack.includes(filters.query));
  });
}

function subscriptionCard(sub) {
  return `
    <article class="subscription-card ${sub.enabled ? "" : "is-disabled"}">
      <div class="subscription-card-head">
        <div class="subscription-avatar" aria-hidden="true">${escapeHtml(initialText(sub.username || sub.uid))}</div>
        <div class="subscription-title">
          <h2>${escapeHtml(sub.username || "未命名 UP 主")}</h2>
          <p class="mono">UID ${escapeHtml(sub.uid || "-")}</p>
        </div>
        ${statusPill(sub.enabled ? "启用" : "停用", sub.enabled)}
      </div>
      <div class="subscription-meta">
        <div>
          <span>类型</span>
          <strong>${typeBadge(sub.sub_type)}</strong>
        </div>
        <div>
          <span>会话</span>
          <strong class="mono">${escapeHtml(sub.target_id || "-")}</strong>
        </div>
      </div>
      ${labelsBlock(sub)}
      <div class="subscription-actions">
        <button class="ghost-button" type="button" data-toggle="1"
          data-uid="${escapeAttribute(sub.uid)}" data-sub-type="${escapeAttribute(sub.sub_type)}"
          data-target-id="${escapeAttribute(sub.target_id)}" data-enabled="${escapeAttribute(String(!sub.enabled))}">
          ${sub.enabled ? "停用" : "启用"}
        </button>
        <button class="danger-button" type="button" data-delete="1"
          data-uid="${escapeAttribute(sub.uid)}" data-sub-type="${escapeAttribute(sub.sub_type)}"
          data-target-id="${escapeAttribute(sub.target_id)}">删除</button>
      </div>
    </article>
  `;
}

function labelsBlock(sub) {
  const labels = [...(sub.categories || []), ...(sub.tags || [])].filter(Boolean);
  if (!labels.length) {
    return `<div class="subscription-labels muted">未设置分类或标签</div>`;
  }
  return `
    <div class="subscription-labels">
      ${labels.slice(0, 6).map((label) => `<span>${escapeHtml(label)}</span>`).join("")}
    </div>
  `;
}

function summaryBadge(label, value) {
  return `<span><strong>${escapeHtml(value)}</strong>${escapeHtml(label)}</span>`;
}

function initialText(value) {
  return String(value || "UP").trim().slice(0, 2).toUpperCase();
}
