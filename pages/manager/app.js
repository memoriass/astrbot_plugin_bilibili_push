import { createApi, getBridge } from "./api.js";
import { renderOverview } from "./overview.js";
import {
  renderAccounts,
  renderDiagnostics,
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
    { onToggle: toggleSubscription, onDelete: deleteSubscription },
  );
  renderAccounts(document.getElementById("accountsPanel"), overview.accounts || []);
  renderPending(document.getElementById("pendingPanel"), overview.pending_tasks || [], {
    onClear: clearPending,
  });
  renderDiagnostics(
    document.getElementById("diagnosticsPanel"),
    overview.diagnostics || {},
    overview.subscriptions || [],
    { onManualLive: manualLiveCheck },
  );
  renderTemplates(
    document.getElementById("templatesPanel"),
    state.previews,
    state.selectedPreview,
    { onPreview: loadTemplatePreview, onGenerate: generateTemplates },
  );
}

function switchTab(tab) {
  state.tab = tab || "overview";
  render();
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
  if (!window.confirm("重新生成模板预览会启动浏览器渲染，继续？")) {
    return;
  }
  try {
    showToast("正在生成模板预览");
    const result = await api.generateTemplates(dateSeed());
    state.previews = result.previews || [];
    state.selectedPreview = null;
    render();
    showToast("模板预览已生成");
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
