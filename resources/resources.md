# resources 模块

`resources` 保留给插件级静态资源。目前运行时资源集中放在 `utils/resources/` 和 `pages/manager/assets/`。

## 文件职责

- 当前没有运行时必需资源。
- 推送卡片和模板资源放在 `utils/resources/`。
- Plugin Pages 前端资源放在 `pages/manager/`。

## 接手注意

- 推送卡片模板在 `utils/resources/templates/`，不要混放。
- Plugin Pages 已放在 `pages/`，不要复用旧聊天 help 资源结构。
