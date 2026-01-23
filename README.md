# Bilibili 推送插件

基于 [nonebot-bison](https://github.com/MountainDash/nonebot-bison) 项目重写的 AstrBot Bilibili 推送插件。

## 功能特性

- ✅ **动态订阅**：订阅 UP 主的动态更新（视频、专栏、图片、转发等）
- ✅ **直播订阅**：订阅 UP 主的直播状态（开播、下播、标题更新）
- ✅ **分类过滤**：支持按动态分类过滤推送内容
- ✅ **标签过滤**：支持按话题标签过滤推送内容
- ✅ **自动推送**：定时检查并自动推送到指定群组
- ✅ **持久化存储**：订阅数据本地保存，重启不丢失

## 安装

1. 将插件文件夹复制到 AstrBot 的 `data/plugins/` 目录下
2. 安装依赖：
   ```bash
   pip install httpx pydantic
   ```

## 配置

在插件配置文件中添加以下配置（或复制 `config.yaml.example` 为 `config.yaml`）：

```yaml
# 推送目标群组 ID (必填)
target_group_id: "123456789"

# 平台名称 (auto 为自动检测)
platform_name: "auto"

# 检查间隔（秒）
check_interval: 30

# 数据存储路径
data_dir: "./data/bilibili_push"
```

### 配置说明

- **target_group_id**: 推送消息的目标群组 ID（必填）
- **platform_name**: 消息平台名称，`auto` 为自动检测，也可指定 `llonebot`、`napcat` 等
- **check_interval**: 检查订阅更新的时间间隔，单位为秒，建议 30-60 秒
- **data_dir**: 订阅数据和状态的存储目录

## 使用方法

### 基本命令

#### 1. 添加动态订阅
```
bilibili 添加订阅 <UID>
```
订阅指定 UP 主的所有动态更新。

**示例**：
```
bilibili 添加订阅 546195
```

#### 2. 添加直播订阅
```
bilibili 添加直播 <UID>
```
订阅指定 UP 主的直播状态（开播、下播提醒）。

**示例**：
```
bilibili 添加直播 546195
```

#### 3. 删除订阅
```
bilibili 删除订阅 <UID> [类型]
```
删除指定 UP 主的订阅。类型可选 `dynamic`（动态）或 `live`（直播），默认为 `dynamic`。

**示例**：
```
bilibili 删除订阅 546195
bilibili 删除订阅 546195 live
```

#### 4. 查看订阅列表
```
bilibili 订阅列表
```
查看当前所有订阅。

#### 5. 查看插件状态
```
bilibili 状态
```
查看插件运行状态和统计信息。

### 获取 UP 主 UID

1. **方法一**：访问 UP 主主页，URL 中的数字即为 UID
   ```
   https://space.bilibili.com/546195
   ↑ UID 是 546195
   ```

2. **方法二**：在 UP 主主页按 F12 打开开发者工具，在控制台输入：
   ```javascript
   window.__INITIAL_STATE__.mid
   ```

## 动态分类说明

插件支持以下动态分类：

| 分类 ID | 说明 |
|---------|------|
| 1 | 一般动态（图片、图文） |
| 2 | 专栏文章 |
| 3 | 视频 |
| 4 | 纯文字 |
| 5 | 转发 |
| 6 | 直播推送 |

## 直播分类说明

直播订阅支持以下分类：

| 分类 ID | 说明 |
|---------|------|
| 1 | 开播提醒 |
| 2 | 标题更新提醒 |
| 3 | 下播提醒 |

默认订阅开播和下播提醒（分类 1 和 3）。

## 数据存储

插件会在配置的 `data_dir` 目录下创建以下文件：

- `subscriptions.json`: 订阅列表
- `state.json`: 订阅状态（用于检测新动态）

这些文件会自动创建和更新，无需手动编辑。

## 注意事项

1. **检查间隔**：建议设置为 30-60 秒，过短可能导致请求过于频繁
2. **首次订阅**：首次添加订阅时，不会推送历史动态，只推送新发布的内容
3. **UID 格式**：UID 必须是纯数字，不支持用户名
4. **群组 ID**：确保配置的 `target_group_id` 正确，否则无法推送消息

## 技术架构

```
astrbot_plugin_bilibili_push/
├── main.py                 # 插件主入口
├── platform/               # 平台实现层
│   └── bilibili/          # Bilibili 平台
│       ├── client.py      # API 客户端
│       ├── parser.py      # 动态解析器
│       ├── live.py        # 直播处理器
│       └── models.py      # 数据模型
├── post/                  # 消息封装层
│   ├── post.py           # Post 数据类
│   └── protocol.py       # 协议定义
├── scheduler/             # 调度系统
│   └── scheduler.py      # 定时任务调度
├── sub_manager/          # 订阅管理
│   └── storage.py        # 数据持久化
└── utils/                # 工具模块
    ├── types.py          # 类型定义
    └── http_client.py   # HTTP 客户端
```

## 致谢

本插件基于 [nonebot-bison](https://github.com/MountainDash/nonebot-bison) 项目重写，保留了其核心的 Bilibili API 调用逻辑和数据模型，特此感谢原项目的贡献者们。

## 许可证

MIT License

## 更新日志

### v1.0.0 (2026-01-22)

- 🎉 初始版本发布
- ✅ 支持 Bilibili 动态订阅
- ✅ 支持 Bilibili 直播订阅
- ✅ 支持分类和标签过滤
- ✅ 自动推送到群组
