const bridge = window.AstrBotPluginPage || createLocalBridge();

const state = {
  tab: "subscriptions",
  overview: null,
  query: "",
  type: "all",
};

const metrics = document.getElementById("metrics");
const toast = document.getElementById("toast");
const searchInput = document.getElementById("searchInput");
const typeFilter = document.getElementById("typeFilter");
const subscriptionToolbar = document.getElementById("subscriptionToolbar");

document.getElementById("refreshButton").addEventListener("click", loadOverview);
searchInput.addEventListener("input", () => {
  state.query = searchInput.value.trim().toLowerCase();
  render();
});
typeFilter.addEventListener("change", () => {
  state.type = typeFilter.value;
  render();
});

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => {
    state.tab = button.dataset.tab;
    render();
  });
});

await bridge.ready();
await loadOverview();

async function loadOverview() {
  try {
    showLoading();
    state.overview = unwrap(await bridge.apiGet("overview"));
    render();
  } catch (error) {
    showToast(error.message || String(error));
    renderEmptyError();
  }
}

function render() {
  const overview = state.overview || {};
  renderMetrics(overview.diagnostics || {});
  renderTabs();
  renderSubscriptions(overview.subscriptions || []);
  renderAccounts(overview.accounts || []);
  renderPending(overview.pending_tasks || []);
}

function renderMetrics(diagnostics) {
  const items = [
    ["总订阅", diagnostics.subscriptions || 0],
    ["启用", diagnostics.enabled_subscriptions || 0],
    ["动态", diagnostics.dynamic_subscriptions || 0],
    ["直播", diagnostics.live_subscriptions || 0],
    ["账号", `${diagnostics.valid_accounts || 0}/${diagnostics.accounts || 0}`],
    ["Pending", diagnostics.pending_tasks || 0],
  ];
  metrics.innerHTML = items
    .map(
      ([label, value]) => `
        <article class="metric">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </article>
      `,
    )
    .join("");
}

function renderTabs() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === state.tab);
  });
  document.querySelectorAll(".panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `${state.tab}Panel`);
  });
  subscriptionToolbar.hidden = state.tab !== "subscriptions";
}

function renderSubscriptions(subscriptions) {
  const panel = document.getElementById("subscriptionsPanel");
  const filtered = subscriptions.filter((sub) => {
    const haystack = `${sub.uid} ${sub.username} ${sub.target_id}`.toLowerCase();
    const typeMatched = state.type === "all" || sub.sub_type === state.type;
    return typeMatched && (!state.query || haystack.includes(state.query));
  });
  if (!filtered.length) {
    panel.innerHTML = emptyState("没有匹配的订阅");
    return;
  }
  panel.innerHTML = `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>UP 主</th>
            <th>UID</th>
            <th>类型</th>
            <th>会话</th>
            <th>状态</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${filtered.map(subscriptionRow).join("")}
        </tbody>
      </table>
    </div>
  `;
  panel.querySelectorAll("[data-toggle]").forEach((button) => {
    button.addEventListener("click", () => toggleSubscription(button.dataset));
  });
  panel.querySelectorAll("[data-delete]").forEach((button) => {
    button.addEventListener("click", () => deleteSubscription(button.dataset));
  });
}

function subscriptionRow(sub) {
  return `
    <tr class="${sub.enabled ? "" : "disabled-row"}">
      <td class="strong">${escapeHtml(sub.username || "-")}</td>
      <td>${escapeHtml(sub.uid)}</td>
      <td>${typeBadge(sub.sub_type)}</td>
      <td class="mono">${escapeHtml(sub.target_id)}</td>
      <td>${statusPill(sub.enabled ? "启用" : "停用", sub.enabled)}</td>
      <td class="right">
        <button
          class="ghost-button"
          type="button"
          data-toggle="1"
          data-uid="${escapeAttribute(sub.uid)}"
          data-sub-type="${escapeAttribute(sub.sub_type)}"
          data-target-id="${escapeAttribute(sub.target_id)}"
          data-enabled="${escapeAttribute(String(!sub.enabled))}"
        >${sub.enabled ? "停用" : "启用"}</button>
        <button
          class="danger-button"
          type="button"
          data-delete="1"
          data-uid="${escapeAttribute(sub.uid)}"
          data-sub-type="${escapeAttribute(sub.sub_type)}"
          data-target-id="${escapeAttribute(sub.target_id)}"
        >删除</button>
      </td>
    </tr>
  `;
}

async function toggleSubscription(dataset) {
  const uid = dataset.uid;
  const subType = dataset.subType;
  const targetId = dataset.targetId;
  const enabled = dataset.enabled === "true";
  try {
    unwrap(
      await bridge.apiPost("subscriptions/enabled", {
        uid,
        sub_type: subType,
        target_id: targetId,
        enabled,
      }),
    );
    showToast(enabled ? "订阅已启用" : "订阅已停用");
    await loadOverview();
  } catch (error) {
    showToast(error.message || String(error));
  }
}

async function deleteSubscription(dataset) {
  const uid = dataset.uid;
  const subType = dataset.subType;
  const targetId = dataset.targetId;
  if (!window.confirm(`删除 ${uid} / ${subType} 订阅？`)) {
    return;
  }
  try {
    unwrap(
      await bridge.apiPost("subscriptions/delete", {
        uid,
        sub_type: subType,
        target_id: targetId,
      }),
    );
    showToast("订阅已删除");
    await loadOverview();
  } catch (error) {
    showToast(error.message || String(error));
  }
}

function renderAccounts(accounts) {
  const panel = document.getElementById("accountsPanel");
  if (!accounts.length) {
    panel.innerHTML = emptyState("暂无登录账号");
    return;
  }
  panel.innerHTML = `
    <div class="cards">
      ${accounts
        .map(
          (account) => `
            <article class="account-card">
              <img src="${escapeAttribute(account.face || "")}" alt="" />
              <div>
                <h2>${escapeHtml(account.name || "Bilibili 账号")}</h2>
                <p class="mono">UID ${escapeHtml(account.uid || "-")}</p>
              </div>
              ${statusPill(account.valid ? "有效" : "失效", account.valid)}
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderPending(tasks) {
  const panel = document.getElementById("pendingPanel");
  if (!tasks.length) {
    panel.innerHTML = emptyState("暂无 pending 任务");
    return;
  }
  panel.innerHTML = `
    <div class="pending-actions">
      <button class="danger-button" id="clearPendingButton" type="button">清空 Pending</button>
    </div>
    <div class="cards">
      ${tasks.map(pendingCard).join("")}
    </div>
  `;
  document
    .getElementById("clearPendingButton")
    .addEventListener("click", clearPending);
}

function pendingCard(task) {
  const expires = task.expires_at ? new Date(task.expires_at * 1000) : null;
  return `
    <article class="pending-card">
      <div>
        <h2>${escapeHtml(task.task_id)}</h2>
        <p>${escapeHtml(task.kind || task.workflow || "-")}</p>
      </div>
      <dl>
        <div><dt>来源</dt><dd class="mono">${escapeHtml(task.origin || "-")}</dd></div>
        <div><dt>候选</dt><dd>${escapeHtml(task.candidate_count || 0)}</dd></div>
        <div><dt>过期</dt><dd>${escapeHtml(expires ? formatTime(expires) : "-")}</dd></div>
      </dl>
    </article>
  `;
}

async function clearPending() {
  if (!window.confirm("清空所有 pending 任务？")) {
    return;
  }
  try {
    const result = unwrap(await bridge.apiPost("pending/clear", {}));
    showToast(`已清空 ${result.cleared || 0} 个任务`);
    await loadOverview();
  } catch (error) {
    showToast(error.message || String(error));
  }
}

function showLoading() {
  metrics.innerHTML = "";
  document.getElementById("subscriptionsPanel").innerHTML = emptyState("加载中");
  document.getElementById("accountsPanel").innerHTML = emptyState("加载中");
  document.getElementById("pendingPanel").innerHTML = emptyState("加载中");
}

function renderEmptyError() {
  metrics.innerHTML = "";
  document.getElementById("subscriptionsPanel").innerHTML = emptyState("加载失败");
  document.getElementById("accountsPanel").innerHTML = emptyState("加载失败");
  document.getElementById("pendingPanel").innerHTML = emptyState("加载失败");
}

function emptyState(text) {
  return `<div class="empty">${escapeHtml(text)}</div>`;
}

function typeBadge(value) {
  const text = value === "live" ? "直播" : "动态";
  return `<span class="badge ${escapeAttribute(value)}">${text}</span>`;
}

function statusPill(text, ok) {
  return `<span class="pill ${ok ? "ok" : "bad"}">${escapeHtml(text)}</span>`;
}

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    toast.hidden = true;
  }, 2400);
}

function unwrap(response) {
  if (response?.status === "ok") {
    return response.data || {};
  }
  if (response?.status === "error") {
    throw new Error(response.message || "请求失败");
  }
  return response || {};
}

function formatTime(date) {
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttribute(value) {
  return escapeHtml(value);
}

function createLocalBridge() {
  return {
    ready: async () => ({}),
    apiGet: async () => ({
      status: "ok",
      data: {
        diagnostics: {
          subscriptions: 4,
          enabled_subscriptions: 3,
          dynamic_subscriptions: 2,
          live_subscriptions: 2,
          targets: 2,
          accounts: 2,
          valid_accounts: 1,
          pending_tasks: 1,
        },
        subscriptions: [
          {
            uid: "946974",
            username: "哔哩哔哩番剧",
            sub_type: "dynamic",
            target_id: "aiocqhttp:GroupMessage:10001",
            enabled: true,
          },
          {
            uid: "19577966",
            username: "哔哩哔哩直播",
            sub_type: "live",
            target_id: "aiocqhttp:GroupMessage:10001",
            enabled: false,
          },
        ],
        accounts: [
          { uid: "10001", name: "Bili Account", face: "", valid: true },
          { uid: "10002", name: "Backup Account", face: "", valid: false },
        ],
        pending_tasks: [
          {
            task_id: "bili1a2b3c4d",
            kind: "up_candidates",
            workflow: "add_subscription",
            origin: "aiocqhttp:GroupMessage:10001",
            candidate_count: 3,
            expires_at: Date.now() / 1000 + 120,
          },
        ],
      },
    }),
    apiPost: async () => ({ status: "ok", data: { removed: true, cleared: 1 } }),
  };
}
