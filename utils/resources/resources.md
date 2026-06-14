# utils resources 模块

`utils/resources` 放渲染所需资源。

## 文件职责

- `templates/`: Jinja2 HTML 模板。
- `backgrounds/`: 默认背景图。

## 接手注意

- 这里服务推送和命令卡片渲染。
- 资源路径由 `utils/resource.py` 读取，不要在业务模块硬编码绝对路径。
