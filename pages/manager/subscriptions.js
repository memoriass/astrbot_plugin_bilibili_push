import {
  bindDataset,
  emptyState,
  escapeAttribute,
  escapeHtml,
  statusPill,
  typeBadge,
} from "./utils.js";

const NO_FACE = "http://i0.hdslb.com/bfs/face/member/noface.jpg";
const CATEGORY_OPTIONS = {
  dynamic: [
    [1, "一般动态"],
    [2, "专栏文章"],
    [3, "视频"],
    [4, "纯文字"],
    [5, "转发"],
    [6, "直播推送"],
  ],
  live: [
    [1, "开播提醒"],
    [2, "标题更新"],
    [3, "下播提醒"],
  ],
};

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
      actions.onSubmit(editorPayload(form));
    });
    panel.querySelector("[data-cancel-subscription]").addEventListener("click", actions.onCancel);
    form.querySelector("[name='sub_type']").addEventListener("change", (event) => {
      const type = event.target.value;
      form.querySelector(".category-options").innerHTML = categoryControls(
        type,
        defaultCategories(type),
      );
    });
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
      <div class="subscription-media">
        <img src="${escapeAttribute(sub.face || NO_FACE)}" alt="" onerror="this.src='${NO_FACE}'" />
        <div class="subscription-card-badges">
          ${sub.sub_type === "live" ? `<span class="media-badge live">LIVE</span>` : ""}
          ${sub.sub_type === "dynamic" ? `<span class="media-badge dyn">DYNAMIC</span>` : ""}
        </div>
        <div class="subscription-media-overlay">
          <h2>${escapeHtml(sub.username || "未命名 UP 主")}</h2>
          <p>UID: ${escapeHtml(sub.uid || "-")}</p>
        </div>
      </div>
      <div class="subscription-status-row">
        ${statusPill(sub.enabled ? "启用" : "停用", sub.enabled)}
        <span class="mono">${escapeHtml(sub.target_id || "-")}</span>
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
  const subType = item.sub_type || "dynamic";
  return `
    <form class="subscription-editor" id="subscriptionEditorForm">
      <input type="hidden" name="mode" value="${escapeAttribute(editor.mode || "create")}" />
      <input type="hidden" name="original_uid" value="${escapeAttribute(item.original_uid || item.uid || "")}" />
      <input type="hidden" name="original_sub_type" value="${escapeAttribute(item.original_sub_type || item.sub_type || "")}" />
      <input type="hidden" name="original_target_id" value="${escapeAttribute(item.original_target_id || item.target_id || "")}" />
      <div class="editor-heading">
        <div>
          <h2>${editor.mode === "edit" ? "编辑订阅" : "新增订阅"}</h2>
          <p>选择订阅类型后勾选需要推送的通知类别；Cookie 和账号不在这里处理。</p>
        </div>
        <button class="ghost-button" type="button" data-cancel-subscription="1">取消</button>
      </div>
      <div class="subscription-editor-layout">
        ${editorPreview(item, editor.mode)}
        <div class="subscription-editor-fields">
          <div class="editor-grid">
            ${field("UID", "uid", item.uid || "", "text", true)}
            ${field("UP 主", "username", item.username || "", "text", false)}
            ${selectField("类型", "sub_type", subType)}
            ${field("会话 ID", "target_id", item.target_id || "", "text", true)}
          </div>
          <section class="category-panel">
            <div>
              <h3>通知类别</h3>
              <p>默认已按当前类型选中常用类别，可按会话需求调整。</p>
            </div>
            <div class="category-options">
              ${categoryControls(subType, item.categories || defaultCategories(subType))}
            </div>
          </section>
          <label class="tag-field">
            <span>标签</span>
            <input name="tags" type="text" value="${escapeAttribute(listText(item.tags))}" placeholder="可选，多个标签用逗号分隔" />
          </label>
        </div>
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

function editorPreview(item, mode) {
  const subType = item.sub_type || "dynamic";
  return `
    <div class="subscription-editor-preview">
      <img src="${escapeAttribute(item.face || NO_FACE)}" alt="" onerror="this.src='${NO_FACE}'" />
      <div class="subscription-card-badges">
        <span class="media-badge ${subType === "live" ? "live" : "dyn"}">${subType === "live" ? "LIVE" : "DYNAMIC"}</span>
      </div>
      <span class="editor-preview-action">${mode === "edit" ? "EDIT" : "ADD"}</span>
      <div class="subscription-media-overlay">
        <h2>${escapeHtml(item.username || "待选择 UP 主")}</h2>
        <p>UID: ${escapeHtml(item.uid || "-")}</p>
      </div>
    </div>
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

function categoryControls(subType, selected) {
  const selectedSet = new Set((selected || []).map((item) => String(item)));
  return CATEGORY_OPTIONS[subType].map(([value, label]) => `
    <label class="category-chip">
      <input type="checkbox" name="categories" value="${escapeAttribute(value)}"
        ${selectedSet.has(String(value)) ? "checked" : ""} />
      <span>${escapeHtml(label)}</span>
    </label>
  `).join("");
}

function defaultCategories(subType) {
  return CATEGORY_OPTIONS[subType].map(([value]) => value);
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

function editorPayload(form) {
  const formData = new FormData(form);
  return {
    mode: formData.get("mode"),
    original_uid: formData.get("original_uid"),
    original_sub_type: formData.get("original_sub_type"),
    original_target_id: formData.get("original_target_id"),
    uid: formData.get("uid"),
    username: formData.get("username"),
    sub_type: formData.get("sub_type"),
    target_id: formData.get("target_id"),
    categories: formData.getAll("categories"),
    tags: formData.get("tags"),
    enabled: formData.get("enabled") === "true",
  };
}
