# manager 页面

`manager` 是 AstrBot WebUI 中的插件管理页，用于集中查看 Bilibili Push 的运行状态。

## 文件职责

- `index.html`: 页面结构和静态资源引用。
- `app.js`: Bridge 初始化、状态管理和页面动作编排。
- `api.js`: bridge API endpoint 封装和响应解包。
- `overview.js`: 概览工作台渲染，会话聚合、待处理项、模板入口和能力摘要。
- `subscriptions.js`: 订阅卡片渲染、筛选和启停/删除动作绑定。
- `renderers.js`: 各标签页渲染函数。
- `utils.js`: HTML 转义、格式化和通用 UI 片段。
- `mock_bridge.js`: 本地预览 fallback 数据。
- `style.css`: 亮暗主题、响应式布局和通用组件样式。
- `overview.css`: 概览工作台布局和卡片样式。
- `subscriptions.css`: 订阅卡片、订阅摘要和移动端布局样式。
- `views.css`: 诊断和模板预览标签页样式。

## 数据来源

- `bridge.apiGet("overview")`
- `bridge.apiGet("templates/list")`
- `bridge.apiGet("templates/preview", params)`
- `bridge.apiPost("subscriptions/enabled", body)`
- `bridge.apiPost("subscriptions/delete", body)`
- `bridge.apiPost("checks/live", body)`
- `bridge.apiPost("pending/clear", body)`
- `bridge.apiPost("templates/generate", body)`

这些 endpoint 由 `webapi/manager_api.py` 注册。

## 边界

- 当前页面不新增订阅。
- 概览页只聚合已有 API 数据，不直接新增后端状态。
- 手动直播检查会向目标会话发送当前正在直播的启用订阅。
- 模板预览重新生成会启动浏览器渲染，并可能访问 Bilibili 热门接口取样例数据。
- 启停和删除订阅必须传完整 `uid + sub_type + target_id`。
- 本地直接打开页面时使用 `mock_bridge.js` 内的假数据 fallback，仅用于布局预览。
- 账号卡片不展示 cookies。
