import {
  bindDataset,
  emptyState,
  escapeAttribute,
  escapeHtml,
  formatBytes,
  formatTime,
  statusPill,
  typeBadge,
} from "./utils.js";

export function renderOverview(panel, overview, previews, actions) {
  const diagnostics = overview.diagnostics || {};
  const subscriptions = overview.subscriptions || [];
  const accounts = overview.accounts || [];
  const pendingTasks = overview.pending_tasks || [];
  const sessions = buildSessions(subscriptions);
  const issues = buildIssues(subscriptions, accounts, pendingTasks, previews);

  panel.innerHTML = `
    <section class="overview-layout">
      <div class="overview-main">
        ${workbenchSummary(diagnostics, issues)}
        <section class="overview-section">
          <div class="section-heading">
            <div>
              <p class="section-kicker">会话</p>
              <h2>会话工作台</h2>
            </div>
            <button class="ghost-button" type="button" data-jump="subscriptions">订阅管理</button>
          </div>
          ${sessionGrid(sessions)}
        </section>
      </div>
      <aside class="overview-side">
        ${issuePanel(issues)}
        ${templatePanel(previews)}
        ${capabilityPanel(diagnostics)}
      </aside>
    </section>
  `;

  bindDataset(panel, "[data-jump]", (dataset) => actions.onNavigate(dataset.jump));
  bindDataset(panel, "[data-live]", (dataset) => actions.onManualLive(dataset.targetId));
  bindDataset(panel, "[data-preview]", actions.onPreview);
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

function sessionGrid(sessions) {
  if (!sessions.length) {
    return emptyState("暂无会话订阅");
  }
  return `<div class="session-grid">${sessions.map(sessionCard).join("")}</div>`;
}

function sessionCard(session) {
  const topSubscriptions = session.subscriptions.slice(0, 4).map(subscriptionLine).join("");
  const more = Math.max(session.subscriptions.length - 4, 0);
  return `
    <article class="session-card">
      <div class="session-card-head">
        <div>
          <h3 class="mono">${escapeHtml(session.target_id)}</h3>
          <p>${escapeHtml(session.enabled)} 启用 / ${escapeHtml(session.disabled)} 停用</p>
        </div>
        ${statusPill(`${session.enabled}/${session.total}`, session.enabled > 0)}
      </div>
      <div class="session-stat-row">
        ${miniStat("动态", session.dynamic)}
        ${miniStat("直播", session.live)}
        ${miniStat("总数", session.total)}
      </div>
      <div class="subscription-lines">
        ${topSubscriptions}
        ${more ? `<p class="muted-line">另有 ${escapeHtml(more)} 个订阅</p>` : ""}
      </div>
      <div class="session-actions">
        <button class="ghost-button" type="button" data-live="1" data-target-id="${escapeAttribute(session.target_id)}">直播检查</button>
        <button class="ghost-button" type="button" data-jump="subscriptions">查看订阅</button>
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

function capabilityPanel(diagnostics) {
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
    </section>
  `;
}

function buildSessions(subscriptions) {
  const sessions = new Map();
  for (const sub of subscriptions) {
    const targetId = sub.target_id || "-";
    const session = sessions.get(targetId) || {
      target_id: targetId,
      total: 0,
      enabled: 0,
      disabled: 0,
      dynamic: 0,
      live: 0,
      subscriptions: [],
    };
    session.total += 1;
    session.enabled += sub.enabled ? 1 : 0;
    session.disabled += sub.enabled ? 0 : 1;
    session.dynamic += sub.sub_type === "dynamic" ? 1 : 0;
    session.live += sub.sub_type === "live" ? 1 : 0;
    session.subscriptions.push(sub);
    sessions.set(targetId, session);
  }
  return Array.from(sessions.values()).sort((a, b) => b.total - a.total);
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

function subscriptionLine(sub) {
  return `
    <div class="subscription-line">
      <span>${escapeHtml(sub.username || sub.uid || "-")}</span>
      ${typeBadge(sub.sub_type)}
    </div>
  `;
}

function factItem(label, value) {
  return `<article><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`;
}

function miniStat(label, value) {
  return `<span><strong>${escapeHtml(value)}</strong>${escapeHtml(label)}</span>`;
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
