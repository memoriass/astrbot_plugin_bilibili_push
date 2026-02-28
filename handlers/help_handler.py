from pathlib import Path
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context
from astrbot.api import logger
import astrbot.api.message_components as Comp

from ..utils.html_renderer import HtmlRenderer
from ..utils.resource import get_random_background, get_template_path, get_assets_path

class HelpHandler:
    def __init__(self, context: Context, bg_dir: Path):
        self.context = context
        self.renderer = HtmlRenderer(get_template_path())
        self.bg_folder = bg_dir

    async def handle_help(self, event: AstrMessageEvent):
        """处理 B站 插件帮助命令"""
        categories = [
            {
                "name": "动态追踪", "desc": "关注 UP 主最新动态",
                "commands": [
                    {"name": "添加b站订阅 <UID>", "desc": "追踪该 UID 的每一条动态", "eg": "添加b站订阅 123456"},
                    {"name": "取消b站订阅 <UID>", "desc": "停止追踪该 UID 的动态"},
                    {"name": "b站订阅列表", "desc": "查看本群/私聊的所有订阅情况"}
                ]
            },
            {
                "name": "直播提醒", "desc": "开播瞬间即刻送达",
                "commands": [
                    {"name": "添加b站直播 <UID>", "desc": "该 UP 主开播时推送提醒", "eg": "添加b站直播 123456"},
                    {"name": "取消b站直播 <UID>", "desc": "不再接收开播提醒"}
                ]
            },
            {
                "name": "账号与工具", "desc": "更稳定的内容解析",
                "commands": [
                    {"name": "b站登录", "desc": "扫码登录 B站 账号，提升身份减少风控"},
                    {"name": "b站登录状态", "desc": "查看当前已登录的账号池状态"},
                    {"name": "b站搜索 <关键词>", "desc": "在 B站 快速搜索 UP 主并获取 UID", "eg": "b站搜索 灵笼"}
                ]
            },
            {
                "name": "内容解析", "desc": "链接即得内容详情",
                "commands": [
                    {"name": "链接预览", "desc": "自动识别 B站 视频或动态链接并生成预览"},
                    {"name": "短链解析", "desc": "支持 b23.tv 等短链接自动解析显示"}
                ]
            }
        ]

        bg_data = get_random_background(self.bg_folder)
        try:
            img_bytes = await self.renderer.render(
                "help_menu.html.jinja",
                {"categories": categories, "bg_image_uri": bg_data["uri"]},
                viewport={"width": 800, "height": 800},
                selector=".help-container"
            )
            yield event.chain_result([Comp.Image.fromBytes(img_bytes)])
        except Exception as e:
            logger.error(f"Help render failed: {e}")
            yield event.plain_result(f"❌ 生成帮助菜单失败: {e}")
