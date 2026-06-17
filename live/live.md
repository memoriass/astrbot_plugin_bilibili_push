# live 模块

`live` 负责 Bilibili 直播状态订阅链路。

## 文件职责

- `bilibili.py`: 获取直播状态、对比状态变化、生成直播推送 `Post`。

## 状态含义

- `0`: 未开播。
- `1`: 直播中。
- `2`: 轮播。

## 维护说明

- 状态变化判断集中在 `Info.get_live_action()` 和 `compare_status()`。
- 推送分类目前为开播、标题更新、下播。
- 直播订阅的轮询和缓存不在本模块，位于 `scheduler/`。
- 本模块只负责把接口状态转换成直播 `Post`，不处理会话分组、启停过滤或消息发送。
- 修改直播状态枚举时，需要同步 `scheduler/live_checker.py` 的缓存比较和 WebUI 手动检查展示。
- Bilibili 接口异常应向上暴露，让调度器决定是否保留旧状态。
