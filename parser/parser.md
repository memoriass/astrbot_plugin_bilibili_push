# parser 模块

`parser` 负责从普通聊天文本中识别 Bilibili 链接并查询详情。

## 文件职责

- `bilibili_parser.py`: 识别 BV、av、动态、opus、直播间、b23 短链。

## 接手注意

- 这里服务链接自动解析，不负责订阅推送。
- 短链解析依赖 HTTP 跳转，异常时应降级为不解析。
- 返回结构直接喂给 `parser_bili.html.jinja`，新增字段需同步模板。
