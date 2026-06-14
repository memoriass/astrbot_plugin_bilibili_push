# workflows 模块

`workflows` 放 Bilibili AI workflow 编排层。它把 LLM tool、显式命令和 pending 续跑统一成 `WorkflowRequest`，再分发到具体业务 handler。

## 文件职责

- `models.py`: workflow 定义、别名、确认/取消词。
- `parsing_tool.py`: LLM tool 参数解析。
- `parsing_command.py`: 显式 workflow 命令和 pending 短命令解析。
- `parsing_natural.py`: 本地自然语言意图解析。
- `runner.py`: workflow 分发表。
- `runtime.py`: 事件文本、会话来源和 tool event 适配。
- `pending.py`: pending task 创建、候选选择和确认续跑。
- `pending_store.py`: pending task KV 持久化、匹配、过期清理。
- `search.py`: UP 主搜索 workflow。
- `subscription.py`: 添加、确认添加和删除订阅 workflow。
- `manage.py`: 订阅列表、账号状态和诊断 workflow。
- `formatting.py`: workflow 输出文本格式化。
- `filters.py`: AstrBot pending shortcut filter。

## 边界

- `main.py` 只注册入口，不承载 workflow 业务。
- `handlers/ai_handler.py` 只做 Agent 入口和旧工具兼容。
- 搜索候选多于 0 个时，如果要写订阅，必须先生成 pending task 并确认。
- 明确 UID 的添加订阅可以直接写库，但仍限定当前会话。
- 删除订阅必须使用当前事件的 `unified_msg_origin`。
- pending task 默认写入 AstrBot KV，重载插件后仍可在有效期内继续。

## 当前 workflow

- `search_up`
- `add_subscription`
- `remove_subscription`
- `list_subscriptions`
- `account_status`
- `check_status`
- `continue_pending`
