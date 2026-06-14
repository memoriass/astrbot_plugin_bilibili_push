import {
  bindDataset,
  emptyState,
  escapeAttribute,
  escapeHtml,
  statusPill,
  typeBadge,
} from "./utils.js";

export function renderSubscriptionCards(panel, subscriptions, filters, actions, editor) {
  const filtered = filterSubscriptions(subscriptions, filters);
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
        <button class="ghost-button" type="button" data-create-subscription="1">新增订阅</button>
      </div>
    </section>
    ${editor ? editorForm(editor) : ""}
    <section class="subscription-card-grid">
      ${filtered.length ? filtered.map(subscriptionCard).join("") : emptyState("没有匹配的订阅")}
    </section>
  `;
  panel.querySelector("[data-create-subscription]").addEventListener("click", actions.onCreate);
  bindDataset(panel, "[data-edit]", actions.onEdit);
  bindDataset(panel, "[data-toggle]", actions.onToggle);
  bindDataset(panel, "[data-delete]", actions.onDelete);
  const form = panel.querySelector("#subscriptionEditorForm");
  if (form) {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      actions.onSubmit(Object.fromEntries(new FormData(form)));
    });
    panel.querySelector("[data-cancel-subscription]").addEventListener("click", actions.onCancel);
  }
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
        <button class="ghost-button" type="button" data-edit="1"
          data-uid="${escapeAttribute(sub.uid)}" data-sub-type="${escapeAttribute(sub.sub_type)}"
          data-target-id="${escapeAttribute(sub.target_id)}">编辑</button>
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

function editorForm(editor) {
  const item = editor.item || {};
  return `
    <form class="subscription-editor" id="subscriptionEditorForm">
      <input type="hidden" name="mode" value="${escapeAttribute(editor.mode || "create")}" />
      <input type="hidden" name="original_uid" value="${escapeAttribute(item.original_uid || item.uid || "")}" />
      <input type="hidden" name="original_sub_type" value="${escapeAttribute(item.original_sub_type || item.sub_type || "")}" />
      <input type="hidden" name="original_target_id" value="${escapeAttribute(item.original_target_id || item.target_id || "")}" />
      <div class="editor-heading">
        <div>
          <h2>${editor.mode === "edit" ? "编辑订阅" : "新增订阅"}</h2>
          <p>分类用逗号分隔；动态默认 1-6，直播默认 1-3。</p>
        </div>
        <button class="ghost-button" type="button" data-cancel-subscription="1">取消</button>
      </div>
      <div class="editor-grid">
        ${field("UID", "uid", item.uid || "", "text", true)}
        ${field("UP 主", "username", item.username || "", "text", false)}
        ${selectField("类型", "sub_type", item.sub_type || "dynamic")}
        ${field("会话 ID", "target_id", item.target_id || "", "text", true)}
        ${field("分类", "categories", listText(item.categories), "text", false)}
        ${field("标签", "tags", listText(item.tags), "text", false)}
      </div>
      <label class="editor-check">
        <input type="checkbox" name="enabled" value="true" ${item.enabled === false ? "" : "checked"} />
        启用订阅
      </label>
      <div class="editor-actions">
        <button class="ghost-button" type="submit">${editor.mode === "edit" ? "保存修改" : "创建订阅"}</button>
      </div>
    </form>
  `;
}

function field(label, name, value, type, required) {
  return `
    <label>
      <span>${escapeHtml(label)}</span>
      <input name="${escapeAttribute(name)}" type="${escapeAttribute(type)}"
        value="${escapeAttribute(value)}" ${required ? "required" : ""} />
    </label>
  `;
}

function selectField(label, name, value) {
  return `
    <label>
      <span>${escapeHtml(label)}</span>
      <select name="${escapeAttribute(name)}">
        <option value="dynamic" ${value === "dynamic" ? "selected" : ""}>动态</option>
        <option value="live" ${value === "live" ? "selected" : ""}>直播</option>
      </select>
    </label>
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

function listText(value) {
  return Array.isArray(value) ? value.join(",") : (value || "");
}

function initialText(value) {
  return String(value || "UP").trim().slice(0, 2).toUpperCase();
}
