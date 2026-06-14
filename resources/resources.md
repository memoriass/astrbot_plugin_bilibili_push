# resources 模块

`resources` 放插件级静态资源。

## 文件职责

- 当前没有运行时必需资源；推送卡片和模板资源放在 `utils/resources/`。

## 接手注意

- 推送卡片模板在 `utils/resources/templates/`，不要混放。
- 后续如果接入 Plugin Pages，可在根目录新增 `pages/`，不要复用旧聊天 help 资源结构。
