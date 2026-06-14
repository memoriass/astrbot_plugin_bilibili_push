# utils 模块

`utils` 放渲染、资源和日志等辅助能力。

## 文件职责

- `html_renderer.py`: Playwright 浏览器生命周期和 HTML 截图。
- `resource.py`: 模板、背景图等资源路径和读取。
- `logger.py`: AstrBot logger 适配器。
- `renderers/`: 推送卡片主题。
- `resources/`: 内置模板和默认背景图。

## 接手注意

- 浏览器生命周期由 `BrowserManager` 管理，关闭逻辑由调度器和插件生命周期触发。
- 模板渲染失败通常会影响用户可见结果，调用方应返回可读错误。
- 新模板应放到 `utils/resources/templates/`。
- `HtmlRenderer` 默认输出透明 PNG；模板外层背景应保持 transparent。
