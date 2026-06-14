# live 模块

`live` 负责 Bilibili 直播状态订阅链路。

## 文件职责

- `bilibili.py`: 获取直播状态、对比状态变化、生成直播推送 `Post`。

## 状态含义

- `0`: 未开播。
- `1`: 直播中。
- `2`: 轮播。

## 接手注意

- 状态变化判断集中在 `Info.get_live_action()` 和 `compare_status()`。
- 推送分类目前为开播、标题更新、下播。
- 直播订阅的轮询和缓存不在本模块，位于 `scheduler/`。
