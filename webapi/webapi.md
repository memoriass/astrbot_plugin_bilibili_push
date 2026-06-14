# webapi 模块

`webapi` 负责 AstrBot Plugin Pages 使用的后端接口。它只做 Web API 注册、请求解析和响应序列化，不承载聊天命令和 workflow 业务。

## 文件职责

- `manager_api.py`: 注册管理页 API，并提供订阅、账号、pending task、诊断动作入口。
- `template_preview.py`: 模板预览列表、单图读取和重新生成。
- `__init__.py`: 对外暴露 `register_bilibili_web_apis()`。

## 当前路由

注册前缀固定为 `/astrbot_plugin_bilibili_push/`，由 AstrBot Dashboard 转发为 `/api/plug/<plugin>/<endpoint>`。

- `GET overview`: 返回订阅、账号、pending task 和运行统计；订阅会补充头像和直播状态用于卡片预览。
- `POST checks/live`: 对指定会话执行手动直播检查。
- `POST subscriptions/delete`: 按 `uid + sub_type + target_id` 删除订阅。
- `POST subscriptions/enabled`: 按 `uid + sub_type + target_id` 启用或停用订阅。
- `POST pending/clear`: 清空 workflow pending task。
- `GET templates/list`: 列出本地模板预览 PNG。
- `GET templates/preview`: 读取单个模板预览为 data URL。
- `POST templates/generate`: 重新生成模板预览 PNG。

## 边界

- `main.py` 只调用注册函数，不写具体接口逻辑。
- 接口返回普通 dict，避免给本插件增加新的顶层 Web 依赖。
- POST 读取 JSON 时在函数内部惰性导入 `quart.request`。
- 账号输出必须过滤 cookies 等敏感字段。
- 写操作必须参数完整，不做模糊匹配。
- 手动直播检查会触发实际消息推送，页面侧必须显式确认。
- 模板预览生成可调用浏览器渲染和 Bilibili 样例接口，不放进 overview。
