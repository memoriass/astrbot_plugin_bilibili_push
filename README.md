# AstrBot Bilibili Push

用于 AstrBot 的 Bilibili 订阅推送插件。支持订阅 UP 主动态、直播状态提醒、Bilibili 链接自动解析，并提供 Web 管理页。

## 主要功能

- 订阅 UP 主动态，自动推送视频、专栏、图文等新动态。
- 订阅 UP 主直播状态，推送开播、标题变化和下播提醒。
- 自动识别聊天中的 Bilibili 视频、动态、opus、直播间和短链。
- 使用透明背景卡片展示订阅列表、账号状态、搜索候选和确认流程。
- 在 AstrBot 插件页面中进入 `manager` 管理订阅、账号、待处理事项和手动直播检查。
- 可接入 AstrBot AI，让用户用自然语言搜索、查看和管理订阅；写入订阅前仍会要求用户确认。

## 快速使用

实际命令前缀以 AstrBot 的 `wake_prefix` 为准，下方用 `<wake_prefix>` 表示。

| 用途 | 命令 |
| :--- | :--- |
| 订阅动态 | `<wake_prefix> 添加b站订阅 <UID>` |
| 订阅直播 | `<wake_prefix> 添加b站直播 <UID>` |
| 删除动态订阅 | `<wake_prefix> 取消b站订阅 <UID>` |
| 删除直播订阅 | `<wake_prefix> 取消b站直播 <UID>` |
| 查看订阅 | `<wake_prefix> b站订阅列表` |
| 搜索 UP 主 | `<wake_prefix> b站搜索 <关键词>` |
| 登录 Bilibili 账号 | `<wake_prefix> b站登录` |
| 查看账号状态 | `<wake_prefix> b站登录状态` |
| 显式 AI 命令 | `<wake_prefix> b站助手 <自然语言>` |

示例：

```text
<wake_prefix> 添加b站订阅 946974
<wake_prefix> b站搜索 影视飓风
<wake_prefix> b站助手 帮我搜索影视飓风并订阅动态
```

## AI 使用说明

AI 能帮助执行搜索、查看订阅、添加订阅、删除订阅等操作。用户只给出 UP 主名称时，插件会先搜索候选；如果候选置信度很高，会自动进入确认流程，但不会直接写入订阅。

最终写入订阅仍需要用户引用确认卡片回复“确认”。如果候选不明确，用户需要先引用候选卡片回复序号。

插件已经注册 Bilibili 专用 AI 工具。正常对话中，只要 AstrBot 当前模型和会话启用了工具调用，大模型可以在用户自然语言提到 B站、UP 主、动态订阅或直播订阅时自动调用工具；`b站助手` 只是手动指定“这句话交给插件 AI 流程处理”的显式入口。

## Web 管理页

在 AstrBot 插件详情页打开 `manager` 页面，可进行：

- 查看运行概览、订阅数量、账号状态和待处理事项。
- 新增、编辑、启停、删除订阅。
- 新增、编辑、删除 Bilibili 登录账号，并标记账号有效性。
- 按群会话执行手动直播检查，或选择全部检查。
- 清空过期或不再需要的待处理任务。

Web 管理页不提供模板预览功能；模板预览仅作为开发脚本使用。

## 常用配置

- `enable_link_parser`: 是否启用链接自动解析，默认开启。
- `check_interval`: 周期检查间隔，建议 30-60 秒。
- `search_cache_expiry_hours`: 搜索缓存有效期。
- `enable_ai_tools`: 是否注册 AI 工具。
- `enable_ai_agent_entry`: 是否启用 `b站助手` 显式入口。
- `ai_tool_timeout_sec`: AI 工具调用超时时间。
- `ai_max_steps`: AI Agent 最大执行步数。
- `ai_pending_timeout_sec`: AI 待处理任务有效期。
- `enable_ai_auto_select_candidates`: AI/自然语言模糊订阅时，是否允许高置信候选自动进入确认流程。
- `ai_auto_select_confidence`: 自动候选选择阈值，默认 `0.88`。
- `verify_ssl`: HTTPS 请求是否校验证书，建议保持开启。

## 注意事项

- 建议登录 Bilibili 账号以提升接口稳定性。
- 每个订阅绑定当前会话；同一 UP 可在不同群或不同订阅类型下分别管理。
- 删除、编辑和启停订阅会按 `UID + 类型 + 会话` 精确定位。
- 透明卡片会使用聊天程序自身背景，推送动态和直播卡片仍保留原有 HTML 模板风格。

## 许可证

MIT License
