# workflows 模块

`workflows` 放 Bilibili AI workflow 编排层。它把 LLM tool、显式命令和 pending 续跑统一成 `WorkflowRequest`，再分发到具体业务 handler。

## 文件职责

- `models.py`: workflow 定义、别名、确认/取消词。
- `parsing_tool.py`: LLM tool 参数解析。
- `parsing_command.py`: 显式 workflow 命令和 pending 短命令解析。
- `parsing_natural.py`: 本地自然语言意图解析。
- `runner.py`: workflow 分发表。
- `runtime.py`: 事件文本、引用消息文本包、会话来源和 tool event 适配。
- `markers.py`: 将后台 task id 编码为不可见 marker，用于引用消息续跑。
- `results.py`: workflow 文本结果和可选卡片数据结构。
- `cards.py`: 将搜索候选、订阅列表、账号状态和订阅变更转换为模板数据。
- `presenter.py`: 显式聊天入口的 HTML 模板渲染和消息组件组装。
- `pending.py`: pending task 创建、引用 marker 解析、候选选择和确认续跑。
- `pending_store.py`: pending task KV 持久化、匹配、过期清理。
- `search.py`: UP 主搜索 workflow。
- `subscription.py`: 添加、确认添加和删除订阅 workflow。
- `manage.py`: 订阅列表、账号状态和诊断 workflow。
- `formatting.py`: workflow 输出文本格式化。
- `filters.py`: AstrBot pending shortcut filter。

## 边界

- `main.py` 只注册入口，不承载 workflow 业务。
- `handlers/ai_handler.py` 只做 Agent 入口和旧工具兼容。
- workflow handler 返回 `WorkflowResult`，其中 `text` 是后端和 LLM 工具使用的稳定文本。
- 显式命令和 pending 续跑可通过 `presenter.py` 把 `WorkflowResult.cards` 渲染为 HTML 图片卡片。
- LLM tool 只返回 `WorkflowResult.text`，不要把图片消息组件传给模型。
- 用户侧不展示 task id；显式聊天入口会在文本中附加不可见 marker，pending 入口会从引用消息文本包解析 marker 并续跑。
- `bili<任务ID>` 显式输入仍保留为兼容入口，但不作为主引导文案。
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

## 聊天卡片

- `search_up` 和模糊 `add_subscription`: 使用 `workflow_candidates.html.jinja` 展示候选 UP 和引用回复方式。
- `list_subscriptions`: 使用 `sub_list.html.jinja` 展示当前会话订阅。
- `account_status`: 使用 `sub_list.html.jinja` 展示账号池状态。
- 确认 pending: 使用 `workflow_confirm.html.jinja` 展示引用回复确认和取消方式。
- `add_subscription` 和 `remove_subscription` 成功后: 使用 `sub_add.html.jinja` 展示订阅变更。
- `check_status` 仍保持纯文本，避免诊断信息被卡片截断。
