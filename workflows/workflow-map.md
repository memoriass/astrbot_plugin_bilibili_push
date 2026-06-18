# Bilibili Workflow 图谱

本文档用于快速检查 `astrbot_plugin_bilibili_push` 当前 workflow、分叉关系、AI 介入点和确认边界。后续新增 workflow 时，应同步更新本文档和 `workflows.md`。

VSCode 图形文件：

- `workflows/workflow-map.drawio`: 用 VSCode Draw.io Integration 扩展打开，可图形化查看和编辑。
- `workflows/workflow-map.mmd`: Mermaid 源文件，可用 Mermaid 预览扩展打开，也便于 diff。

## 总览

```mermaid
flowchart TD
    Entry["用户自然语言 / 命令 / LLM tool"] --> Request["WorkflowRequest"]
    Request --> Runner["runner.py 统一分发"]
    Runner --> Dispatch["ai_dispatch 前置分流"]
    Runner --> Direct["显式 workflow"]

    Dispatch --> Branches["branches.py 本地候选分支"]
    Dispatch --> Semantic["semantic_dispatch.py LLM + 语义召回"]
    Semantic --> Select["选择受控分支"]
    Branches --> Select

    Select --> Search["search_up"]
    Select --> Add["add_subscription"]
    Select --> Remove["remove_subscription"]
    Select --> Lists["list_* / find_subscription"]
    Select --> Diagnose["diagnose_* / account_status"]
    Select --> LiveCheck["check_live_*"]

    Direct --> Search
    Direct --> Add
    Direct --> Remove
    Direct --> Lists
    Direct --> Diagnose
    Direct --> LiveCheck
    Direct --> Pending["continue_pending"]

    Search --> CandidateCard["候选卡 / AI 推荐"]
    Add --> Resolve["实体解析 / 当前会话别名"]
    Resolve --> SharedAlias["跨会话共享证据"]
    SharedAlias --> BiliSearch["Bili 搜索兜底"]
    BiliSearch --> CandidateAI["candidate_analysis.py"]
    CandidateAI --> AddConfirm["确认订阅卡"]
    Remove --> CurrentSubs["当前会话订阅候选"]
    CurrentSubs --> RemoveAI["AI 候选分析"]
    RemoveAI --> RemoveConfirm["确认删除卡"]

    Lists --> ListCard["订阅列表卡"]
    Diagnose --> Text["诊断文本"]
    LiveCheck --> CurrentLive["当前群直接检查"]
    LiveCheck --> AllLiveConfirm["全部群检查确认卡"]

    CandidateCard --> Pending
    AddConfirm --> Pending
    RemoveConfirm --> Pending
    AllLiveConfirm --> Pending

    Pending --> Write["确认后写库 / 删除 / 执行检查"]
    Pending --> Cancel["取消或过期"]
```

## AI 可选分叉

| 分叉 | 实际 workflow | 类型 | 是否写库 | 是否确认 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `search_up` | `search_up` | 只读 | 否 | 否 | 搜索 UP，纯搜索不会转订阅 |
| `add_dynamic` | `add_subscription` | 写操作前置 | 否 | 是 | 添加动态订阅，确认后写库 |
| `add_live` | `add_subscription` | 写操作前置 | 否 | 是 | 添加直播订阅，确认后写库 |
| `add_both` | `add_subscription` | 写操作前置 | 否 | 是 | 同时添加动态和直播，确认后写库 |
| `remove_dynamic/live/both` | `remove_subscription` | 写操作前置 | 否 | 是 | 删除当前会话订阅，确认后删除 |
| `list_all_subscriptions` | `list_all_subscriptions` | 只读 | 否 | 否 | 查看当前会话全部订阅 |
| `list_live_subscriptions` | `list_live_subscriptions` | 只读 | 否 | 否 | 查看当前会话直播订阅 |
| `list_dynamic_subscriptions` | `list_dynamic_subscriptions` | 只读 | 否 | 否 | 查看当前会话动态订阅 |
| `find_subscription` | `find_subscription` | 只读 | 否 | 否 | 在当前会话订阅和历史别名中查找 |
| `account_status` | `account_status` | 只读 | 否 | 否 | 查看账号池状态 |
| `diagnose_health` | `diagnose_health` | 只读 | 否 | 否 | 检查数据库、账号池、pending、调度器和渲染器 |
| `diagnose_resolver` | `diagnose_resolver` | 只读 | 否 | 否 | 查看别名命中、搜索回退和歧义统计 |
| `check_live_current_group` | `check_live_current_group` | 请求型 | 否 | 否 | 手动检查当前会话直播订阅 |
| `check_live_all_groups` | `check_live_all_groups` | 请求型 | 否 | 是 | 需要确认后检查全部群直播订阅 |
| `continue_pending` | `continue_pending` | 续跑 | 视任务而定 | 已由任务决定 | 处理引用序号、确认和取消 |

## 关键链路

### 添加订阅

```mermaid
flowchart LR
    Text["添加订阅自然语言"] --> Dispatch["ai_dispatch"]
    Dispatch --> Add["add_subscription"]
    Add --> UID["明确 UID"]
    Add --> Alias["当前订阅 / 本群别名"]
    Add --> Shared["共享别名证据"]
    Add --> Search["Bili 搜索"]
    Search --> AI["AI 候选分析"]
    UID --> Confirm["确认订阅卡"]
    Alias --> Confirm
    Shared --> Confirm
    Shared --> Search
    AI --> Confirm
    AI --> Candidates["候选卡"]
    Candidates --> Continue["引用序号"]
    Continue --> Confirm
    Confirm --> User["引用确认"]
    User --> DB["写入 SQLite"]
```

### 删除订阅

```mermaid
flowchart LR
    Text["删除订阅自然语言"] --> Dispatch["ai_dispatch"]
    Dispatch --> Remove["remove_subscription"]
    Remove --> Scope["限定当前会话订阅"]
    Scope --> Alias["UID / 名称 / 别名"]
    Scope --> AI["AI 当前订阅候选分析"]
    Alias --> Confirm["确认删除卡"]
    AI --> Confirm
    AI --> Candidates["删除候选卡"]
    Candidates --> Continue["引用序号"]
    Continue --> Confirm
    Confirm --> User["引用确认删除"]
    User --> DB["按 UID + 类型 + 会话删除"]
```

### 管理与诊断

```mermaid
flowchart TD
    Dispatch["ai_dispatch"] --> ListAll["list_all_subscriptions"]
    Dispatch --> ListLive["list_live_subscriptions"]
    Dispatch --> ListDynamic["list_dynamic_subscriptions"]
    Dispatch --> Find["find_subscription"]
    Dispatch --> Account["account_status"]
    Dispatch --> Health["diagnose_health"]
    Dispatch --> Resolver["diagnose_resolver"]

    ListAll --> SubCard["订阅卡"]
    ListLive --> SubCard
    ListDynamic --> SubCard
    Find --> SubCard
    Account --> AccountCard["账号卡"]
    Health --> HealthText["健康诊断文本"]
    Resolver --> ResolverText["解析诊断文本"]
```

### 直播检查

```mermaid
flowchart TD
    Dispatch["ai_dispatch"] --> Current["check_live_current_group"]
    Dispatch --> All["check_live_all_groups"]
    Current --> ManualCurrent["读取当前会话启用直播订阅"]
    ManualCurrent --> PushCurrent["开播则推送"]
    All --> Confirm["全部群检查确认卡"]
    Confirm --> Continue["continue_pending"]
    Continue --> ManualAll["读取全部启用直播订阅"]
    ManualAll --> Dedup["按 UID 分组去重"]
    Dedup --> PushAll["开播则按目标分发"]
```

## 确认边界

- `add_subscription` 不直接写库；明确 UID、高置信候选、候选序号选择后都必须进入确认卡。
- `remove_subscription` 只在当前会话订阅内定位目标，确认删除后才删除。
- `check_live_all_groups` 会触发全局直播请求，必须先生成确认任务。
- `search_up`、`list_*`、`find_subscription`、`account_status`、`diagnose_*` 都是只读，不需要确认。
- `continue_pending` 只接受引用消息、唯一 pending 兜底或明确短词，避免普通聊天误触。
- 跨会话共享别名只在至少两个会话确认同一 UID 且无竞争 UID 时自动推进；有冲突时降级到搜索或候选卡。

## 维护说明

- 新增 workflow: 先改 `models.py` 和 `runner.py`，再在 `branches.py` 加受控分支。
- 新增 AI 可选分支: 必须加入 `ALLOWED_NEXT_WORKFLOWS`，并确认 `semantic_dispatch.py` 的 prompt 使用动态 allowed list。
- 新增写操作: 必须有 pending task 和确认卡，不能由 LLM 直接写库。
- 新增请求型操作: 至少要评估限频、确认边界和日志输出。
