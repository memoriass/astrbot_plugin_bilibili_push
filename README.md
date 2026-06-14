# AstrBot Bilibili Push 📺

订阅 Bilibili UP 主动态和直播状态，自动推送到群聊。支持高性能图片渲染、分类过滤及链接自动解析。

## ⚡ 快速开始

1. **添加订阅**：使用 `<wake_prefix> 添加b站订阅 <UID>` 即可订阅动态，使用 `<wake_prefix> 添加b站直播 <UID>` 订阅直播。
2. **搜索并订阅**：如果不记得 UID，可以使用 `<wake_prefix> b站搜索 <关键词>` 查找 UP 主。
3. **查看列表**：发送 `<wake_prefix> b站订阅列表` 查看并管理当前会话的所有订阅。

> 示例（以生产配置为例）：`plana 添加b站订阅 946974`
> 实际前缀以 AstrBot 的 `wake_prefix` 配置为准。

---

## 📸 指令说明

| 指令 | 别名示例 | 说明 |
| :--- | :--- | :--- |
| `<wake_prefix> 添加b站订阅 <UID>` | `<wake_prefix> bilibili 添加订阅` | 订阅指定 UP 主的动态（支持视频、专栏、图文等） |
| `<wake_prefix> 添加b站直播 <UID>` | `<wake_prefix> bilibili 添加直播` | 订阅指定 UP 主的直播状态（开播/下播提醒） |
| `<wake_prefix> 取消b站订阅 <UID>` | `<wake_prefix> 删除b站订阅` | 删除指定 UP 主的动态订阅 |
| `<wake_prefix> 取消b站直播 <UID>` | `<wake_prefix> 删除b站直播` | 删除指定 UP 主的直播订阅 |
| `<wake_prefix> b站订阅列表` | `<wake_prefix> bilibili 订阅列表` | 以精美卡片形式查看当前会话的所有订阅 |
| `<wake_prefix> b站搜索 <关键词>` | `<wake_prefix> search_bili` | 在 B站 搜索 UP 主并展示详情卡片 |
| `<wake_prefix> b站登录` | `<wake_prefix> bilibili 登录` | 扫码登录 B站 账号（建议登录以提升稳定性） |
| `<wake_prefix> b站登录状态` | - | 查看登录账号池状态 |
| `<wake_prefix> b站助手 <自然语言>` | `<wake_prefix> bili 助手` | 显式触发 Agent 编排（可选入口） |
| `<wake_prefix> b站工作流 <workflow> [参数]` | `<wake_prefix> biliwf` | 直接执行 Bilibili workflow |

---

## 🤖 AI 工具（Function Calling）

插件已提供以下可被 LLM 调用的工具：

- `bili_workflow`
- `bili_search_up`
- `bili_add_dynamic_sub`
- `bili_add_live_sub`
- `bili_list_subs`
- `bili_remove_sub`

推荐 Agent 优先使用 `bili_workflow`。旧工具保留为兼容入口，会转发到 workflow。
当只提供 UP 名称或模糊关键词时，workflow 会生成 `bili<任务ID>` pending task；
用户选择候选并确认后才会写入订阅。

可通过 `<wake_prefix> tool ls` 查看当前会话可用工具列表。

---

## 🧩 功能特性

- **自动链接解析**：当成员发送 B站 视频或动态链接时，机器人会自动转换成精美详情图。
- **高性能渲染**：基于 Playwright 的内嵌浏览器渲染，默认输出透明 PNG 卡片。
- **视觉增强**：订阅列表、搜索结果和登录账号状态使用透明多卡片布局，聊天背景由平台承接。
- **WebUI 管理页**：在 AstrBot 插件详情页进入 `manager`，可查看订阅、账号、pending task，并执行精确删除。
- **智能清理**：自动清理过期的搜索记录与临时图片文件，节省磁盘空间。

---

## ⚙️ 配置项详解

- **`enable_link_parser`**: 开启/关闭链接自动解析（默认开启）。
- **`check_interval`**: 检查间隔（秒），建议 30-60 秒。
- **`search_cache_expiry_hours`**: 搜索缓存有效期（小时）。
- **`enable_ai_tools`**: 开启/关闭 AI 工具调用。
- **`enable_ai_agent_entry`**: 开启/关闭 `b站助手` 显式 Agent 命令入口。
- **`ai_tool_timeout_sec`**: Agent 工具调用超时（秒）。
- **`ai_max_steps`**: Agent 最大执行步数。
- **`ai_pending_timeout_sec`**: AI workflow pending task 有效期（秒）。
- **`verify_ssl`**: HTTPS 请求是否校验证书（建议保持开启）。

---

## 许可证
MIT License
