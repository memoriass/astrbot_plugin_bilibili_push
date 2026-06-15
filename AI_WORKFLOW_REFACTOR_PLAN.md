# AI Workflow And Plugin Pages Refactor Plan

本文档记录 2026-06-15 的本地接入测试、评审结论和后续改造计划。目标是让 Bilibili 推送插件能更稳定地接入 AstrBot AI，同时为后续 Plugin Pages 管理页预留边界。

## 当前落地状态

已完成：

- 新增 `workflows/` 编排层。
- 新增统一 LLM tool `bili_workflow`。
- 旧 5 个 LLM tools 保留为兼容入口，并转发到 workflow。
- 新增 `b站工作流` 显式命令。
- 新增 `bili<任务ID>` pending task 选择和确认流程。
- pending task 已写入 AstrBot KV，插件重载后仍可在有效期内继续。
- 新增 `pages/manager/` 管理页。
- 新增 `webapi/` 管理页后端 API。
- WebUI 管理页支持订阅启停，调度器只处理启用订阅。
- WebUI 管理页支持订阅/账号管理、pending 清理和手动直播检查。
- `handlers/ai_handler.py` 已退化为 Agent 入口和旧工具适配层。
- workflow 已接入原 HTML 模板卡片；显式命令和 pending 续跑渲染图片，LLM tool 保持文本返回。

未完成：

- WebUI 更完整的诊断日志和批量管理能力。

## 当前接入测试

已完成的本地验证：

- `main.py` AST 检查通过：当前没有 help 命令残留。
- `main.py` AST 检查通过：当前暴露 6 个 LLM tools：
  - `bili_workflow`
  - `bili_search_up`
  - `bili_add_dynamic_sub`
  - `bili_add_live_sub`
  - `bili_list_subs`
  - `bili_remove_sub`
- `scripts/check_workflow_integration.py` 通过，命令、LLM tool、Plugin Pages 和 Web API 注册符合预期。
- 订阅列表和登录账号状态预览仍为透明 PNG，左上角 alpha 为 `0`。
- AstrBot 本地源码可用于源码级对照，`tool_loop_agent`、`register_web_api`、`llm_tool` 相关接口位置已确认。

测试边界：

- 直接导入本地 `C:\git\AstrBot` 运行时失败，原因是当前 Python 环境缺少 AstrBot 运行依赖 `deprecated`。因此本轮只做源码级签名对照，不声称完成 AstrBot 完整运行时集成测试。
- Bilibili 用户搜索接口裸请求会触发 `HTTP 412`；使用插件同款 `httpx` headers 和初始化访问后可返回 `HTTP 200`，但测试关键词可能返回空结果。AI workflow 必须区分网络失败、风控失败、接口成功但无结果。

## Plugin Pages 作用判断

Plugin Pages 用于把插件自己的页面挂进 AstrBot WebUI，适合复杂管理和诊断，不适合作为聊天 help 的替代品。

本插件适合接入的页面：

- `subscriptions`: 订阅列表、启停、删除、按会话筛选。
- `accounts`: 登录账号池、当前账号、风控状态、失效账号标记。
- `overview`: 运行统计、订阅小卡片、待处理项和手动触发检查。

不建议第一阶段接入页面的原因：

- 当前最急的是 AI workflow 的安全边界，尤其是搜索后自动订阅可能误选 UID。
- 第一版 Plugin Pages 已落地为只读概览、精确删除订阅和清空 pending，后续扩展仍应控制写操作范围。
- 简单配置仍应放 `_conf_schema.json`，不要用页面替代配置表单。

## ani-rss Workflow 可学习点

`astrbot_plugin_ani_rss` 的有效模式：

- 一个总 LLM tool 接收 `workflow + target + params`。
- 显式命令、自然语言和 LLM tool 都转换为统一 `WorkflowRequest`。
- `runner.py` 只做分发，不写具体业务。
- 搜索、选择、确认等多步流程通过 pending task 继续执行。
- 复杂候选展示先返回卡片和 task id，不直接写入订阅。

本插件应借鉴该模式，但不要照搬 ANI-RSS 领域概念。

## 改造目标

第一阶段目标：

- 新增 Bilibili workflow 编排层。
- 保留现有 5 个 LLM tools 作为兼容入口。
- 新增一个总工具，例如 `bili_workflow`，用于 Agent 优先调用。
- 将“搜索 UP -> 选择 UP -> 订阅动态/直播”改为 pending workflow，避免模型误选。
- 将 AI 工具业务从 `handlers/ai_handler.py` 中拆出，避免 handler 身兼多职。

第二阶段目标：

- 用 workflow 替代 `b站助手` 当前直接选多个散装 tools 的方式。
- 为 pending task 增加短 ID 继续入口，例如 `bili<id> 1`、`bili<id> 确认`、`bili<id> 取消`。
- 增加只预览、不写库的 workflow，用于 AI 推荐和用户确认。

第三阶段目标：

- 扩展 Plugin Pages 管理页。
- 继续注册只读和低风险 Web API。
- 把订阅增删、账号状态、诊断日志放到 WebUI 中统一管理。

## 建议模块结构

新增目录：

```text
workflows/
├─ __init__.py
├─ workflows.md
├─ models.py
├─ parsing_tool.py
├─ parsing_command.py
├─ parsing_natural.py
├─ runner.py
├─ runtime.py
├─ pending.py
├─ pending_store.py
├─ subscription.py
├─ search.py
├─ manage.py
└─ formatting.py
```

职责边界：

- `models.py`: workflow 定义、别名、确认/取消词、请求模型。
- `parsing_tool.py`: LLM tool 参数解析，不做业务。
- `parsing_command.py`: 显式命令和 pending 短命令解析。
- `parsing_natural.py`: 少量本地中文意图解析，作为非 LLM 入口辅助。
- `runner.py`: workflow 分发入口，只查表和调用 handler。
- `runtime.py`: 回复封装、错误归一化、事件适配。
- `pending.py`: pending task 创建、候选选择和确认续跑。
- `pending_store.py`: pending task KV 持久化、匹配、过期、恢复。
- `search.py`: UP 搜索 workflow，不写订阅。
- `subscription.py`: 添加、预览、确认添加、删除订阅 workflow。
- `manage.py`: 列表、账号状态、诊断 workflow。
- `formatting.py`: 文本和卡片字段格式化。
- `results.py`: workflow 文本结果和可选卡片数据。
- `cards.py`: workflow 复用原 HTML 模板的数据适配。
- `presenter.py`: 显式聊天入口的卡片渲染，LLM tool 不使用。

`handlers/ai_handler.py` 改造后只保留：

- `run_agent()`
- `select workflow tool`
- 旧 LLM tools 的兼容转发

## 建议 Workflow

用户可见 workflow：

- `search_up`: 搜索 UP 主，返回候选和 task id。
- `add_subscription`: 按 UID 添加动态或直播订阅；若来源是搜索候选，必须确认。
- `recommend_subscription`: 根据关键词搜索候选，不直接写库。
- `list_subscriptions`: 当前会话订阅列表。
- `remove_subscription`: 删除当前会话订阅。
- `account_status`: 查看账号池状态。
- `check_status`: 诊断 Bilibili API 和渲染器状态。
- `continue_pending`: 继续候选选择或确认流程。

默认安全策略：

- LLM 不能仅凭模糊搜索结果直接写订阅。
- 搜索结果多于 1 个时必须生成 pending task。
- `add_subscription` 只有明确 UID 时可以直接写库。
- 删除订阅必须限定当前会话 `event.unified_msg_origin`。
- 批量操作默认禁用，除非用户明确指定。

## Plugin Pages 分阶段边界

第一版页面只做管理，不做推送渲染。当前已落地 `pages/manager/`：

- 订阅列表、筛选、精确删除。
- 账号池状态。
- pending task 列表和清空。
- 运行诊断计数。

后端 API 已放到 `webapi/`，不要塞进 `main.py`。

Web API 边界：

- 读接口先行，写接口需要确认参数完整。
- 所有写操作应复用 database/handler/workflow 的同一套服务函数。
- 不在 Page 中直接操作 SQLite。
- Page 前端只访问 `bridge.apiGet()` 和 `bridge.apiPost()`，不手写 Dashboard 路由。

## 文件大小和文档约束

- Python 文件超过 500 行必须拆分。
- Markdown 文档超过 500 行也应按主题拆分。
- `main.py` 只保留装配、命令注册、LLM tool 注册和生命周期。
- 具体业务逻辑不回流到 `main.py`。
- 注释只解释复杂边界，架构说明写入 Markdown。
- 新增模块必须同步对应 `*.md` 模块说明。
- 改 workflow 时同步更新 `ARCHITECTURE.md`、`handlers/handlers.md` 和新增 `workflows/workflows.md`。
- 改模板渲染时同步更新 `utils/resources/templates/templates.md`；模板预览脚本只作为本地开发工具，不接入 WebUI。

## 推荐实施顺序

1. 新增 `workflows/` 骨架和文档，不改变现有行为。
2. 把 `AiToolHandler.search_up/add/remove/list` 迁移到 workflow handler，旧方法转发。
3. 新增 `bili_workflow` LLM tool，并让 `b站助手` 优先只选择该工具。
4. 加入 pending task：搜索候选、选择序号、确认写库。
5. 补本地测试脚本：AST 注册检查、workflow parser、pending 过期和 Web API 注册。
6. 稳定后再添加 Plugin Pages 管理页。
7. 最后考虑下线散装 tools，或保留为兼容 wrapper。

## 验收标准

每个阶段至少通过：

- `python -m compileall -q .`
- `git diff --check`
- 全仓库文本文件行数检查，无文件超过 500 行。
- `scripts/check_workflow_integration.py`
- AST 检查确认命令和 LLM tool 注册符合预期。
- 搜索接口失败时不写订阅、不污染缓存、不吞掉错误。

Plugin Pages 阶段额外要求：

- `pages/<page_name>/index.html` 存在。
- Web API 使用 `context.register_web_api()` 注册，并以插件名为路由前缀。
- 页面刷新后资源路径可用。
- 暗色/亮色主题不遮挡核心操作。
