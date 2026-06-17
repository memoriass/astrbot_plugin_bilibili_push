# handlers 模块

`handlers` 放用户入口适配层，避免 `main.py` 承载具体业务。这里的职责是把 AstrBot 命令、LLM tool、链接解析入口转换为内部服务或 workflow 调用。

## 文件职责

- `subscription_handler.py`: 聊天命令的订阅增删查入口。
- `subscription_editor.py`: 订阅增删和变更卡片。
- `subscription_list.py`: 订阅列表聚合、头像补全、直播状态补全和列表卡片。
- `search_handler.py`: 搜索命令薄适配层，统一转入 `workflows/search.py` 渲染候选卡。
- `ai_handler.py`: LLM tool 适配层，运行统一 workflow，并在 workflow 产出卡片时主动发送给当前会话。
- `login_handler.py`: Bilibili 扫码登录和账号池状态展示。
- `link_handler.py`: 聊天消息里的 Bilibili 链接自动解析。

## 维护说明

- 新命令在 `main.py` 注册，具体业务放入对应 handler 或 `workflows/`。
- Handler 不直接做周期任务；周期行为放 `scheduler/`。
- 聊天侧需要卡片展示时，优先复用 `workflows/presenter.py` 或现有模板，不要在 handler 内重写渲染协议。
- `search_handler.py` 只做命令到 workflow 的适配，不再保留独立 Bilibili 搜索实现。
- `ai_handler.py` 返回给模型的是 `WorkflowResult.text`，但用户侧会收到 `WorkflowResult.cards` 渲染出的 HTML 图片卡片。
- 最终写入订阅仍由 workflow pending 确认控制，AI 工具不得绕过确认直接替用户写入模糊搜索结果。
- Web 管理 API 不放在普通 handler 中，避免聊天入口与 Plugin Pages 管理入口耦合。
- 登录账号状态涉及 Cookie 敏感信息，输出必须过滤 Cookie，只展示账号和有效性状态。
