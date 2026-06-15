# templates 模块

`utils/resources/templates` 放所有图片卡片 HTML 模板。

## 模板职责

- `sub_add.html.jinja`: 添加、删除和 workflow 确认订阅结果卡片。
- `sub_list.html.jinja`: 订阅列表、登录账号状态、搜索结果和 workflow 候选列表复用卡片。
- `parser_bili.html.jinja`: 链接解析卡片。
- `movie_card.html.jinja`: 直播卡片。
- `dynamic_movie_card.html.jinja`: 动态推送卡片。

## 接手注意

- 当前模板按 Playwright 渲染能力设计，使用了 flex/grid/filter 等浏览器 CSS。
- `sub_list.html.jinja` 是透明多卡片模板，用于订阅列表、搜索结果和登录账号状态；不要再加整页背景图。
- 如果引入轻量 HTML 渲染器，应单独维护 lite 模板，避免直接复用这些模板。
- 模板字段来源分散在 `handlers/`、`workflows/cards.py`、`utils/renderers/` 和 `parser/`，改字段时需要同步调用方。
