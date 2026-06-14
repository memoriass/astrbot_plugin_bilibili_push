# renderers 模块

`utils/renderers` 放推送卡片主题，把内部 `Post` 转成 AstrBot 消息组件。

## 文件职责

- `base.py`: 主题抽象基类。
- `movie_card.py`: 直播和类视频卡片主题。
- `dynamic_card.py`: Markdown 风格动态卡片主题，当前主流程主要使用 `dynamic_movie_card` 模板。

## 接手注意

- 新主题应只负责选择模板和组织模板数据。
- 不要在主题里做网络抓取或订阅状态判断。
- 主题返回 AstrBot `message_components` 列表。
