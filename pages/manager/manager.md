# manager 页面

`manager` 是 AstrBot Plugin Pages 中的插件管理页，用于集中查看和维护 Bilibili Push 的运行状态、订阅、登录账号和 pending task。

## 文件职责

- `index.html`: 页面结构、样式和模块入口引用。
- `app.js`: Bridge 初始化、页面状态、tab 切换和用户动作编排。
- `api.js`: `bridge.apiGet()` / `bridge.apiPost()` 的 endpoint 封装。
- `overview.js`: 概览工作台、待处理项和运行能力摘要。
- `subscriptions.js`: 订阅卡片、筛选、新增、编辑、启停和删除交互。
- `accounts.js`: 登录账号卡片、新增、编辑、删除和有效性编辑交互。
- `renderers.js`: 指标、tab、pending 和各模块渲染入口。
- `utils.js`: HTML 转义、格式化和通用 UI 片段。
- `mock_bridge.js`: 本地直接打开页面时的 fallback 假数据。
- `style.css`: 主题变量、基础控件、弹窗和通用组件样式。
- `layout.css`: 页面外壳、左侧导航、顶部栏、指标区和响应式布局样式。
- `flora.css`: 页面和内容区的低透明度欧式绿色藤萝与森系少女装饰背景，引用 `assets/flora-*.svg` 和 `assets/forest-girl-scene.svg`。
- `assets/brand-white-hair.png`: 左侧导航顶部品牌头像图标。
- `overview.css`: 概览工作台和小型订阅卡片样式。
- `subscriptions.css`: 订阅卡片、编辑器和移动端布局样式。
- `accounts.css`: 账号卡片、编辑器和移动端布局样式。

## 数据来源

- `bridge.apiGet("overview")`
- `bridge.apiPost("subscriptions/create", body)`
- `bridge.apiPost("subscriptions/update", body)`
- `bridge.apiPost("subscriptions/enabled", body)`
- `bridge.apiPost("subscriptions/delete", body)`
- `bridge.apiPost("accounts/upsert", body)`
- `bridge.apiPost("accounts/delete", body)`
- `bridge.apiPost("accounts/valid", body)`
- `bridge.apiPost("checks/live", body)`
- `bridge.apiPost("pending/clear", body)`

这些 endpoint 由 `webapi/manager_api.py` 注册。页面不直接访问数据库，也不手写 Dashboard 路由。

## 边界

- 当前页面只覆盖概览、订阅、账号和 pending 管理，不提供模板预览功能。
- 顶部指标卡只在概览页显示，订阅、账号和 pending 页聚焦各自管理内容。
- 概览页承载运行能力摘要和手动直播检查，不再单独提供诊断 tab 或卡片预览。
- 手动直播检查支持“全部检查”，单项检查按启用直播订阅所在群会话聚合，页面只展示短渠道名和群号。
- 订阅列表保留分页控件，默认每页 12 条，筛选条件变化后回到第一页。
- 订阅和账号卡片使用右上角图标按钮承载编辑/删除，编辑和删除确认均通过弹窗完成。
- 订阅卡片列表只显示图片卡片本体；订阅启停、类型和通知类别通过编辑弹窗调整。
- 账号卡片列表只显示头像卡片本体；账号有效性通过编辑弹窗调整。
- 编辑已有订阅时不展示 UID、UP 主和会话 ID 输入，只保留动态/直播类型切换、通知类别、标签和启用状态。
- 启停、编辑和删除订阅必须传完整 `uid + sub_type + target_id`，避免误改同 UID 的其他类型或会话。
- 账号 Cookie 只允许提交写入，不在页面和 `overview` 接口回显。
- 手动直播检查会向目标会话发送当前正在直播的启用订阅，页面侧必须显式确认。
- 本地直接打开页面时使用 `mock_bridge.js` 假数据，只用于布局和交互预览。
