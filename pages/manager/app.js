import { createApi, getBridge } from "./api.js";
import { renderOverview } from "./overview.js";
import {
  renderAccounts,
  renderEmptyError,
  renderMetrics,
  renderPending,
  renderSubscriptions,
  renderTabs,
  renderTemplates,
  showLoading,
} from "./renderers.js";

const bridge = getBridge();
const api = createApi(bridge);

const state = {
  tab: "overview",
  overview: null,
  previews: [],
  selectedPreview: null,
  subscriptionEditor: null,
  accountEditor: null,
  query: "",
  type: "all",
};

const metrics = document.getElementById("metrics");
const toast = document.getElementById("toast");
const searchInput = document.getElementById("searchInput");
const typeFilter = document.getElementById("typeFilter");

document.getElementById("refreshButton").addEventListener("click", refreshAll);
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
    switchTab(button.dataset.tab);
  });
});

await bridge.ready();
await refreshAll();

async function refreshAll() {
  try {
    showLoading(metrics);
    const [overview, templateData] = await Promise.all([
      api.overview(),
      api.listTemplates(),
    ]);
    state.overview = overview;
    state.previews = templateData.previews || [];
    render();
  } catch (error) {
    showToast(error.message || String(error));
    renderEmptyError(metrics);
  }
}

function render() {
  const overview = state.overview || {};
  renderMetrics(metrics, overview.diagnostics || {});
  renderTabs(state.tab);
  renderOverview(
    document.getElementById("overviewPanel"),
    overview,
    state.previews,
    {
      onNavigate: switchTab,
      onManualLive: manualLiveCheck,
      onPreview: previewAndOpenTemplates,
      onGenerate: generateTemplates,
    },
  );
  renderSubscriptions(
    document.getElementById("subscriptionsPanel"),
    overview.subscriptions || [],
    { query: state.query, type: state.type },
    {
      onCreate: startCreateSubscription,
      onEdit: startEditSubscription,
      onSubmit: submitSubscription,
      onCancel: cancelSubscriptionEdit,
      onToggle: toggleSubscription,
      onDelete: deleteSubscription,
    },
    state.subscriptionEditor,
  );
  renderAccounts(
    document.getElementById("accountsPanel"),
    overview.accounts || [],
    {
      onCreate: startCreateAccount,
      onEdit: startEditAccount,
      onSubmit: submitAccount,
      onCancel: cancelAccountEdit,
      onToggleValid: toggleAccountValid,
      onDelete: deleteAccount,
    },
    state.accountEditor,
  );
  renderPending(document.getElementById("pendingPanel"), overview.pending_tasks || [], {
    onClear: clearPending,
  });
  renderTemplates(
    document.getElementById("templatesPanel"),
    state.previews,
    state.selectedPreview,
    {
      seed: dateSeed(),
      onPreview: loadTemplatePreview,
      onGenerate: generateTemplates,
      onRefresh: refreshTemplates,
    },
  );
}

function switchTab(tab) {
  state.tab = tab || "overview";
  render();
}

function startCreateSubscription() {
  const targetId = state.overview?.subscriptions?.[0]?.target_id || "";
  state.subscriptionEditor = {
    mode: "create",
    item: { sub_type: "dynamic", target_id: targetId, enabled: true },
  };
  render();
}

function startEditSubscription(dataset) {
  const item = findSubscription(dataset);
  if (!item) {
    showToast("未找到订阅");
    return;
  }
  state.subscriptionEditor = {
    mode: "edit",
    item: {
      ...item,
      original_uid: item.uid,
      original_sub_type: item.sub_type,
      original_target_id: item.target_id,
    },
  };
  render();
}

function cancelSubscriptionEdit() {
  state.subscriptionEditor = null;
  render();
}

async function submitSubscription(data) {
  const payload = {
    uid: data.uid,
    username: data.username,
    sub_type: data.sub_type,
    target_id: data.target_id,
    categories: data.categories,
    tags: data.tags,
    enabled: data.enabled === "true",
  };
  try {
    if (data.mode === "edit") {
      await api.updateSubscription({
        ...payload,
        original_uid: data.original_uid,
        original_sub_type: data.original_sub_type,
        original_target_id: data.original_target_id,
      });
      showToast("订阅已更新");
    } else {
      await api.createSubscription(payload);
      showToast("订阅已创建");
    }
    state.subscriptionEditor = null;
    await refreshAll();
  } catch (error) {
    showToast(error.message || String(error));
  }
}

function findSubscription(dataset) {
  return (state.overview?.subscriptions || []).find(
    (sub) =>
      String(sub.uid) === String(dataset.uid) &&
      sub.sub_type === dataset.subType &&
      sub.target_id === dataset.targetId,
  );
}

function startCreateAccount() {
  state.accountEditor = { mode: "create", item: { valid: true } };
  render();
}

function startEditAccount(dataset) {
  const item = (state.overview?.accounts || []).find(
    (account) => String(account.uid) === String(dataset.uid),
  );
  if (!item) {
    showToast("未找到账号");
    return;
  }
  state.accountEditor = { mode: "edit", item };
  render();
}

function cancelAccountEdit() {
  state.accountEditor = null;
  render();
}

async function submitAccount(data) {
  try {
    await api.upsertAccount({
      uid: data.uid,
      name: data.name,
      face: data.face,
      cookies_text: data.cookies_text,
      valid: data.valid === "true",
    });
    showToast("账号已保存");
    state.accountEditor = null;
    await refreshAll();
  } catch (error) {
    showToast(error.message || String(error));
  }
}

async function toggleSubscription(dataset) {
  const enabled = dataset.enabled === "true";
  try {
    await api.setSubscriptionEnabled(subscriptionPayload(dataset, { enabled }));
    showToast(enabled ? "订阅已启用" : "订阅已停用");
    await refreshAll();
  } catch (error) {
    showToast(error.message || String(error));
  }
}

async function deleteSubscription(dataset) {
  if (!window.confirm(`删除 ${dataset.uid} / ${dataset.subType} 订阅？`)) {
    return;
  }
  try {
    await api.deleteSubscription(subscriptionPayload(dataset));
    showToast("订阅已删除");
    await refreshAll();
  } catch (error) {
    showToast(error.message || String(error));
  }
}

async function toggleAccountValid(dataset) {
  const valid = dataset.valid === "true";
  try {
    await api.setAccountValid({ uid: dataset.uid, valid });
    showToast(valid ? "账号已标记有效" : "账号已标记失效");
    await refreshAll();
  } catch (error) {
    showToast(error.message || String(error));
  }
}

async function deleteAccount(dataset) {
  if (!window.confirm(`删除 UID ${dataset.uid} 账号？`)) {
    return;
  }
  try {
    await api.deleteAccount({ uid: dataset.uid });
    showToast("账号已删除");
    await refreshAll();
  } catch (error) {
    showToast(error.message || String(error));
  }
}

async function clearPending() {
  if (!window.confirm("清空所有 pending 任务？")) {
    return;
  }
  try {
    const result = await api.clearPending();
    showToast(`已清空 ${result.cleared || 0} 个任务`);
    await refreshAll();
  } catch (error) {
    showToast(error.message || String(error));
  }
}

async function manualLiveCheck(targetId) {
  if (!targetId || !window.confirm(`对 ${targetId} 执行手动直播检查？`)) {
    return;
  }
  try {
    const result = await api.manualLiveCheck(targetId);
    showToast(`手动检查完成，推送 ${result.pushed || 0} 条`);
    await refreshAll();
  } catch (error) {
    showToast(error.message || String(error));
  }
}

async function loadTemplatePreview(dataset) {
  try {
    const result = await api.previewTemplate(dataset.preview);
    state.selectedPreview = result.preview;
    render();
  } catch (error) {
    showToast(error.message || String(error));
  }
}

async function previewAndOpenTemplates(dataset) {
  await loadTemplatePreview(dataset);
  switchTab("templates");
}

async function generateTemplates() {
  const seed = Number(document.getElementById("templateSeedInput")?.value || dateSeed());
  if (!window.confirm("重新生成模板预览会启动浏览器渲染，继续？")) {
    return;
  }
  try {
    showToast("正在生成模板预览");
    const result = await api.generateTemplates(seed);
    state.previews = result.previews || [];
    state.selectedPreview = null;
    render();
    showToast("模板预览已生成");
  } catch (error) {
    showToast(error.message || String(error));
  }
}

async function refreshTemplates() {
  try {
    const result = await api.listTemplates();
    state.previews = result.previews || [];
    render();
    showToast("模板列表已刷新");
  } catch (error) {
    showToast(error.message || String(error));
  }
}

function dateSeed() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return Number(`${now.getFullYear()}${month}${day}`);
}

function subscriptionPayload(dataset, extra = {}) {
  return {
    uid: dataset.uid,
    sub_type: dataset.subType,
    target_id: dataset.targetId,
    ...extra,
  };
}

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    toast.hidden = true;
  }, 2600);
}
