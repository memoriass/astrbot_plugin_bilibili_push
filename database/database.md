# database 模块

`database` 负责 SQLite 持久化。

## 当前数据

- `subscriptions`: 用户订阅，主键为 `uid + sub_type + target_id`，`enabled` 控制是否参与调度。
- `seen_dynamics`: 旧动态去重表，目前主流程使用 AstrBot KV 缓存。
- `live_status`: 旧直播状态表，目前主流程使用 AstrBot KV 缓存。

## 维护说明

- `add_subscription()` 使用普通 `INSERT`，重复订阅返回 `False`，不要改回覆盖写入。
- `get_subscriptions()` 返回全部订阅；调度器应使用 `get_enabled_subscriptions()`。
- `set_subscription_enabled()` 只更新启停状态，不修改分类、标签和用户名。
- 如果新增订阅字段，需要考虑旧库迁移和默认值。
- `_ensure_columns()` 负责旧库轻量迁移，当前会补齐 `enabled` 列。
- SQLite 方法保持同步调用即可，调用频率较低；不要在这里引入 AstrBot 依赖。
- WebUI 和 workflow 写操作必须提供完整定位字段，避免跨会话误改。
- 新增表或字段后，同步更新 `webapi/manager_serializers.py`、`pages/manager/` 表单字段和 `scripts/check_workflow_integration.py` 的覆盖范围。
