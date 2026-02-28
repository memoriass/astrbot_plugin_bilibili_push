from pathlib import Path
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context
from astrbot.api import logger
import astrbot.api.message_components as Comp

from ..utils.html_renderer import HtmlRenderer
from ..utils.resource import get_template_path

class LinkParserHandler:
    def __init__(self, context: Context, template_name="parser_bili"):
        self.context = context
        self.template_name = template_name
        self.renderer = HtmlRenderer(get_template_path())

    async def handle_links(self, event: AstrMessageEvent, parser, enable_link_parser):
        if not enable_link_parser or event.message_str.startswith("/"): return
        info = await parser.parse_message(event.message_str)
        if not info: return
        try:
            # 兼容性处理模板名
            final_template = f"{self.template_name}.html.jinja" if not self.template_name.endswith(".jinja") else self.template_name
            
            img_bytes = await self.renderer.render(
                final_template,
                info,
                viewport={"width": 640, "height": 800},
                selector=".card"
            )
            yield event.chain_result([Comp.Image.fromBytes(img_bytes)])
        except Exception as e: logger.error(f"Link parse render failed: {e}")
