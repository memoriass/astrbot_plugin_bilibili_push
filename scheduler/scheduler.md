# scheduler 模块

`scheduler` 是订阅推送的周期执行器。

## 文件职责

- `scheduler.py`: 读取订阅、分组轮询、动态去重、直播状态缓存、渲染并分发推送。
- `dynamic_checker.py`: 动态订阅检查和动态去重。
- `live_checker.py`: 直播订阅检查、直播状态缓存和手动直播检查。
- `dispatcher.py`: 分类过滤、主题选择、渲染和推送回调。
- `subscription_group.py`: 数据库订阅到 `SubUnit` 的分组转换。

## 接手注意

- 动态去重缓存使用 AstrBot KV，key 形如 `seen_posts_{uid}`。
- 直播状态缓存使用 AstrBot KV，key 形如 `live_status_{uid}`。
- 周期检查和手动直播检查只读取 `enabled=True` 的订阅。
- 新订阅首次动态检查只建立基线，不推送历史动态。
- 网络抓取失败不能更新去重基线。
- `scheduler.py` 是统合入口，不应重新堆入具体动态/直播检查逻辑。
