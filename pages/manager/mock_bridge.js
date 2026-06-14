const samplePreview = encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">
  <rect width="960" height="540" fill="#f6f7f9"/>
  <rect x="80" y="70" width="800" height="400" rx="20" fill="#fff" stroke="#d8dee6"/>
  <text x="120" y="170" font-size="42" font-family="Segoe UI" fill="#17202a">Template Preview</text>
  <text x="120" y="245" font-size="26" font-family="Segoe UI" fill="#64707d">Bilibili Push Manager</text>
  <circle cx="760" cy="260" r="72" fill="#1f7a5c"/>
</svg>
`);

export function createLocalBridge() {
  return {
    ready: async () => ({}),
    apiGet: async (endpoint, params = {}) => {
      if (endpoint === "templates/list") {
        return ok({ previews: mockPreviews() });
      }
      if (endpoint === "templates/preview") {
        const name = params.name || "_contact_sheet.png";
        return ok({
          preview: {
            name,
            label: name.replace(".png", ""),
            size: 880000,
            mtime: Date.now() / 1000,
            data_url: `data:image/svg+xml;charset=utf-8,${samplePreview}`,
          },
        });
      }
      return ok(mockOverview());
    },
    apiPost: async (endpoint) => {
      if (endpoint === "checks/live") {
        return ok({ pushed: 1 });
      }
      if (endpoint === "templates/generate") {
        return ok({ previews: mockPreviews() });
      }
      return ok({ removed: true, updated: true, cleared: 1 });
    },
  };
}

function ok(data) {
  return { status: "ok", data };
}

function mockPreviews() {
  return [
    { name: "_contact_sheet.png", label: "总览拼图", size: 695589, mtime: Date.now() / 1000 },
    { name: "dynamic_movie_card.png", label: "动态推送卡片", size: 2087461, mtime: Date.now() / 1000 },
    { name: "movie_card_live.png", label: "直播推送卡片", size: 1251905, mtime: Date.now() / 1000 },
  ];
}

function mockOverview() {
  return {
    diagnostics: {
      subscriptions: 4,
      enabled_subscriptions: 3,
      dynamic_subscriptions: 2,
      live_subscriptions: 2,
      targets: 2,
      accounts: 2,
      valid_accounts: 1,
      pending_tasks: 1,
      check_interval: 30,
      render_type: "image",
      enable_link_parser: true,
      enable_ai_tools: true,
      enable_ai_agent_entry: true,
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
  };
}
