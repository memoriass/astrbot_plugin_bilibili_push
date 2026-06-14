# manager 页面

`manager` 是 AstrBot WebUI 中的插件管理页，用于集中查看 Bilibili Push 的运行状态。

## 文件职责

- `index.html`: 页面结构和静态资源引用。
- `app.js`: Bridge 初始化、数据加载、标签页切换、筛选、删除订阅、清空 pending。
- `style.css`: 亮暗主题、响应式布局和管理表格样式。

## 数据来源

- `bridge.apiGet("overview")`
- `bridge.apiPost("subscriptions/delete", body)`
- `bridge.apiPost("pending/clear", body)`

这些 endpoint 由 `webapi/manager_api.py` 注册。

## 边界

- 当前页面不新增订阅，不触发手动推送检查。
- 删除订阅必须传完整 `uid + sub_type + target_id`。
- 本地直接打开页面时使用 `app.js` 内的假数据 fallback，仅用于布局预览。
- 账号卡片不展示 cookies。
