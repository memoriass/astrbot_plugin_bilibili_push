# pages 模块

`pages` 放 AstrBot Plugin Pages 前端静态文件。每个一级目录是一页，必须包含 `index.html` 才会被 AstrBot Dashboard 扫描。

## 当前页面

- `manager/`: Bilibili Push 管理面板，详见 `manager/manager.md`。

## 边界

- 页面只通过 `window.AstrBotPluginPage` bridge 调用后端 API。
- 不手写 `/api/plug/...` 绝对路径。
- 不直接读取 Dashboard cookie、LocalStorage 或同源 DOM。
- 不放聊天 help 内容；聊天侧的自然语言能力交给 AI workflow。
- 无构建步骤，静态资源保持相对路径。
