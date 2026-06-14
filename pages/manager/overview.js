import {
  bindDataset,
  emptyState,
  escapeAttribute,
  escapeHtml,
  formatBytes,
  formatTime,
} from "./utils.js";

const NO_FACE = "http://i0.hdslb.com/bfs/face/member/noface.jpg";

export function renderOverview(panel, overview, previews, actions) {
  const diagnostics = overview.diagnostics || {};
  const subscriptions = overview.subscriptions || [];
  const accounts = overview.accounts || [];
  const pendingTasks = overview.pending_tasks || [];
  const targets = Array.from(new Set(subscriptions.map((sub) => sub.target_id))).filter(Boolean);
  const subscriptionPreviews = buildSubscriptionPreviews(subscriptions);
  const issues = buildIssues(subscriptions, accounts, pendingTasks, previews);

  panel.innerHTML = `
    <section class="overview-layout">
      <div class="overview-main">
        ${workbenchSummary(diagnostics, issues)}
        <section class="overview-section">
          <div class="section-heading">
            <div>
              <p class="section-kicker">预览</p>
              <h2>订阅卡片</h2>
            </div>
            <button class="ghost-button" type="button" data-jump="subscriptions">订阅管理</button>
          </div>
          ${subscriptionPreviewGrid(subscriptionPreviews)}
        </section>
      </div>
      <aside class="overview-side">
        ${issuePanel(issues)}
        ${templatePanel(previews)}
        ${capabilityPanel(diagnostics, targets)}
      </aside>
    </section>
  `;

  bindDataset(panel, "[data-jump]", (dataset) => actions.onNavigate(dataset.jump));
  bindDataset(panel, "[data-preview]", actions.onPreview);
  const liveButton = panel.querySelector("[data-live-selected]");
  if (liveButton) {
    liveButton.addEventListener("click", () => {
      actions.onManualLive(panel.querySelector("#overviewManualTargetSelect").value);
    });
  }
  const generateButton = panel.querySelector("[data-generate]");
  if (generateButton) {
    generateButton.addEventListener("click", actions.onGenerate);
  }
}

function workbenchSummary(diagnostics, issues) {
  const total = diagnostics.subscriptions || 0;
  const enabled = diagnostics.enabled_subscriptions || 0;
  const issueCount = issues.reduce((sum, issue) => sum + issue.count, 0);
  const tone = issueCount ? "attention" : "ok";
  const title = issueCount ? "有待处理项" : "运行状态稳定";
  return `
    <section class="workbench-summary ${tone}">
      <div>
        <p class="section-kicker">总览</p>
        <h2>${title}</h2>
        <p>
          已启用 ${escapeHtml(enabled)}/${escapeHtml(total)} 个订阅，
          覆盖 ${escapeHtml(diagnostics.targets || 0)} 个会话，
          当前 pending ${escapeHtml(diagnostics.pending_tasks || 0)} 个。
        </p>
      </div>
      <div class="workbench-facts">
        ${factItem("启用率", ratioText(enabled, total))}
        ${factItem("账号", `${diagnostics.valid_accounts || 0}/${diagnostics.accounts || 0}`)}
        ${factItem("待处理", issueCount)}
      </div>
    </section>
  `;
}

function subscriptionPreviewGrid(previews) {
  if (!previews.length) {
    return emptyState("暂无订阅预览");
  }
  return `<div class="mini-sub-grid">${previews.map(miniSubscriptionCard).join("")}</div>`;
}

function miniSubscriptionCard(sub) {
  return `
    <article class="mini-sub-card ${sub.enabled ? "" : "is-disabled"}">
      <img src="${escapeAttribute(sub.face || NO_FACE)}" alt="" onerror="this.src='${NO_FACE}'" />
      <div class="mini-badges">
        ${sub.has_live ? liveBadge(sub.is_live) : ""}
        ${sub.has_dynamic ? `<span class="mini-badge dyn">DYNAMIC</span>` : ""}
      </div>
      <div class="mini-sub-overlay">
        <h3>${escapeHtml(sub.username || "未命名 UP 主")}</h3>
        <p>UID: ${escapeHtml(sub.uid || "-")}</p>
      </div>
    </article>
  `;
}

function issuePanel(issues) {
  return `
    <section class="overview-section side-section">
      <div class="section-heading">
        <div>
          <p class="section-kicker">队列</p>
          <h2>需要处理</h2>
        </div>
      </div>
      ${issues.length ? `<div class="issue-list">${issues.map(issueRow).join("")}</div>` : emptyState("暂无待处理项")}
    </section>
  `;
}

function templatePanel(previews) {
  const firstPreview = previews[0];
  return `
    <section class="overview-section side-section">
      <div class="section-heading">
        <div>
          <p class="section-kicker">模板</p>
          <h2>模板预览</h2>
        </div>
        <button class="ghost-button" type="button" data-jump="templates">全部</button>
      </div>
      ${
        firstPreview
          ? `
            <article class="template-brief">
              <div>
                <strong>${escapeHtml(previews.length)} 个预览</strong>
                <p>${escapeHtml(firstPreview.label || firstPreview.name)} · ${escapeHtml(formatBytes(firstPreview.size))}</p>
              </div>
              <button class="ghost-button" type="button" data-preview="${escapeAttribute(firstPreview.name)}">查看</button>
            </article>
          `
          : `
            <article class="template-brief">
              <div>
                <strong>暂无预览</strong>
                <p>本地未发现模板预览 PNG。</p>
              </div>
              <button class="ghost-button" type="button" data-generate="1">生成</button>
            </article>
          `
      }
    </section>
  `;
}

function capabilityPanel(diagnostics, targets) {
  return `
    <section class="overview-section side-section">
      <div class="section-heading">
        <div>
          <p class="section-kicker">运行</p>
          <h2>运行能力</h2>
        </div>
      </div>
      <div class="capability-list">
        ${capabilityItem("动态检查", `${diagnostics.check_interval || "-"} 秒`)}
        ${capabilityItem("渲染", diagnostics.render_type || "-")}
        ${capabilityItem("链接解析", diagnostics.enable_link_parser ? "启用" : "停用")}
        ${capabilityItem("AI 工具", diagnostics.enable_ai_tools ? "启用" : "停用")}
        ${capabilityItem("Agent", diagnostics.enable_ai_agent_entry ? "启用" : "停用")}
      </div>
      <div class="overview-live-check">
        <select id="overviewManualTargetSelect" aria-label="目标会话">
          ${targets.map((target) => `<option value="${escapeAttribute(target)}">${escapeHtml(target)}</option>`).join("")}
        </select>
        <button class="ghost-button" type="button" data-live-selected="1" ${targets.length ? "" : "disabled"}>直播检查</button>
      </div>
    </section>
  `;
}

function buildSubscriptionPreviews(subscriptions) {
  const previews = new Map();
  for (const sub of subscriptions) {
    const uid = sub.uid || "-";
    const preview = previews.get(uid) || {
      uid,
      username: sub.username || "",
      face: sub.face || NO_FACE,
      enabled: false,
      has_dynamic: false,
      has_live: false,
      is_live: false,
    };
    preview.username = preview.username || sub.username || "";
    preview.face = preview.face || sub.face || NO_FACE;
    preview.enabled = preview.enabled || Boolean(sub.enabled);
    preview.has_dynamic = preview.has_dynamic || sub.sub_type === "dynamic";
    preview.has_live = preview.has_live || sub.sub_type === "live";
    preview.is_live = preview.is_live || Boolean(sub.is_live);
    previews.set(uid, preview);
  }
  return Array.from(previews.values()).sort((a, b) => Number(b.enabled) - Number(a.enabled));
}

function buildIssues(subscriptions, accounts, pendingTasks, previews) {
  const disabled = subscriptions.filter((sub) => !sub.enabled);
  const invalidAccounts = accounts.filter((account) => !account.valid);
  const issues = [];
  if (pendingTasks.length) {
    issues.push({
      title: "Pending 任务",
      count: pendingTasks.length,
      detail: pendingTasks.slice(0, 2).map((task) => `${task.workflow || task.kind || task.task_id} · ${formatTime(task.expires_at)}`),
      tab: "pending",
    });
  }
  if (invalidAccounts.length) {
    issues.push({
      title: "账号失效",
      count: invalidAccounts.length,
      detail: invalidAccounts.map((account) => account.name || account.uid || "-"),
      tab: "accounts",
    });
  }
  if (disabled.length) {
    issues.push({
      title: "停用订阅",
      count: disabled.length,
      detail: disabled.slice(0, 3).map((sub) => sub.username || sub.uid),
      tab: "subscriptions",
    });
  }
  if (!previews.length) {
    issues.push({
      title: "模板预览缺失",
      count: 1,
      detail: ["需要生成本地预览"],
      tab: "templates",
    });
  }
  return issues;
}

function issueRow(issue) {
  return `
    <article class="issue-row">
      <div>
        <strong>${escapeHtml(issue.title)}</strong>
        <p>${escapeHtml(issue.detail.join(" / "))}</p>
      </div>
      <button class="ghost-button" type="button" data-jump="${escapeAttribute(issue.tab)}">${escapeHtml(issue.count)}</button>
    </article>
  `;
}

function factItem(label, value) {
  return `<article><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`;
}

function liveBadge(isLive) {
  return `<span class="mini-badge ${isLive ? "live-on" : "live-off"}">LIVE</span>`;
}

function capabilityItem(label, value) {
  return `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function ratioText(value, total) {
  if (!total) {
    return "0%";
  }
  return `${Math.round((value / total) * 100)}%`;
}
