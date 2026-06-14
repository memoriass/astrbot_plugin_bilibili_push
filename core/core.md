# core 模块

`core` 放跨模块共享能力，不包含具体命令和推送业务。

## 文件职责

- `types.py`: 插件内部标准类型，如 `Post`、`SubUnit`、`MessageSegment`。
- `models.py`: Bilibili API 的 Pydantic 模型。
- `http.py`: 全局 `httpx.AsyncClient`、Cookie 账号池、风控账号轮换。
- `platform.py`: 动态平台和状态平台的抽象基类。
- `compat.py`: Pydantic v1/v2 兼容入口。
- `runtime.py`: 插件运行期资源初始化、临时文件清理和最终消息发送。
- `utils.py`: 通用算法和 Bilibili WBI 签名。

## 接手注意

- Bilibili API 响应字段变化时，优先更新 `models.py`。
- 任何跨 Pydantic 版本调用应通过 `compat.py`。
- 不要在业务模块里新建长期 HTTP client，统一走 `HttpClient.get_client()`。
- 插件生命周期相关逻辑放 `runtime.py`，不要塞回 `main.py`。
