# templates 模块

`utils/resources/templates` 放所有图片卡片 HTML 模板。

## 模板职责

- `sub_add.html.jinja`: 添加和删除订阅结果卡片。
- `sub_list.html.jinja`: 订阅列表、登录账号状态和旧搜索结果列表复用卡片。
- `workflow_candidates.html.jinja`: workflow 搜索候选卡片，内置 task id 和回复序号提示。
- `workflow_confirm.html.jinja`: workflow 订阅最终确认卡片，内置确认/取消回复提示。
- `parser_bili.html.jinja`: 链接解析卡片。
- `movie_card.html.jinja`: 直播卡片。
- `dynamic_movie_card.html.jinja`: 动态推送卡片。

## 接手注意

- 当前模板按 Playwright 渲染能力设计，使用了 flex/grid/filter 等浏览器 CSS。
- `sub_list.html.jinja` 是透明多卡片模板，用于订阅列表、搜索结果和登录账号状态；不要再加整页背景图。
- workflow 专用模板只承载聊天展示提示；真实写库仍由 `workflows/` pending 确认流程控制。
- 如果引入轻量 HTML 渲染器，应单独维护 lite 模板，避免直接复用这些模板。
- 模板字段来源分散在 `handlers/`、`workflows/cards.py`、`utils/renderers/` 和 `parser/`，改字段时需要同步调用方。
