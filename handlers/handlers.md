# handlers 模块

`handlers` 放用户入口处理逻辑，避免 `main.py` 变成业务大文件。

## 文件职责

- `subscription_handler.py`: 添加、删除、查看订阅。
- `subscription_editor.py`: 订阅增删和变更卡片。
- `subscription_list.py`: 订阅列表聚合、头像/直播状态补充和列表卡片。
- `ai_handler.py`: AI Agent 入口和 LLM tool 的实际业务实现。
- `login_handler.py`: Bilibili 扫码登录和账号池状态展示。
- `search_handler.py`: UP 主搜索和搜索结果卡片。
- `link_handler.py`: 聊天消息中的 Bilibili 链接自动解析。

## 接手注意

- 新命令应在 `main.py` 注册，具体业务放在本目录。
- Handler 不直接做周期任务；周期行为放 `scheduler/`。
- Handler 返回 AstrBot 结果，不应直接调用 `context.send_message()`，除非是明确的跨会话推送。
- 带 AstrBot 装饰器的方法保留在 `main.py`，这里承接实际业务。
- 后续 AI workflow 落地后，`ai_handler.py` 应退化为入口适配层，具体搜索、选择、确认和订阅写入放 `workflows/`。
- Plugin Pages 的 Web API 不放在普通 handler 中，避免聊天入口和 WebUI 管理入口耦合。
