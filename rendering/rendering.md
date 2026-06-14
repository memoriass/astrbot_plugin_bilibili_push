# rendering 模块

`rendering` 定义渲染端口，隔离业务模块和具体 HTML 渲染实现。

## 文件职责

- `renderer_port.py`: 渲染接口协议。
- `html_renderer_adapter.py`: 将 `utils.html_renderer.HtmlRenderer` 适配为端口实现。

## 接手注意

- Handler 和主题渲染应依赖 `RendererPort` 或具体 theme，不直接操作 Playwright。
- 如果未来替换渲染实现，优先在这里加适配器。
- 当前默认输出 PNG，并启用透明背景；需要透明裁剪时优先传具体 selector。
