export function unwrap(response) {
  if (response?.status === "ok") {
    return response.data || {};
  }
  if (response?.status === "error") {
    throw new Error(response.message || "请求失败");
  }
  return response || {};
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function escapeAttribute(value) {
  return escapeHtml(value);
}

export function formatTime(timestamp) {
  if (!timestamp) {
    return "-";
  }
  return new Date(timestamp * 1000).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatBytes(value) {
  const size = Number(value || 0);
  if (size >= 1024 * 1024) {
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
  }
  if (size >= 1024) {
    return `${Math.round(size / 1024)} KB`;
  }
  return `${size} B`;
}

export function emptyState(text) {
  return `<div class="empty">${escapeHtml(text)}</div>`;
}

export function typeBadge(value) {
  const text = value === "live" ? "直播" : "动态";
  return `<span class="badge ${escapeAttribute(value)}">${text}</span>`;
}

export function statusPill(text, ok) {
  return `<span class="pill ${ok ? "ok" : "bad"}">${escapeHtml(text)}</span>`;
}

export function bindDataset(root, selector, handler) {
  root.querySelectorAll(selector).forEach((button) => {
    button.addEventListener("click", () => handler(button.dataset));
  });
}
