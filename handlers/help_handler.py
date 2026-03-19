from pathlib import Path
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context
from astrbot.api import logger
import astrbot.api.message_components as Comp

class HelpHandler:
    def __init__(self, context: Context):
        self.context = context

    async def handle_help(self, event: AstrMessageEvent):
        """处理 B站 插件帮助命令"""
        try:
            # 动态导入避免缓存
            plugin_dir = Path(__file__).parent.parent

            # 使用 importlib.util 动态加载配置文件
            import importlib.util
            config_file = plugin_dir / "resources" / "help" / "help_config.py"
            spec = importlib.util.spec_from_file_location("help_config", config_file)
            help_config_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(help_config_module)

            HELP_CONFIG = help_config_module.HELP_CONFIG
            HELP_LIST = help_config_module.HELP_LIST

            # 导入渲染器
            import sys
            sys.path.insert(0, str(plugin_dir))
            from help_renderer import MiaoHelpRenderer

            # 初始化渲染器
            renderer = MiaoHelpRenderer(plugin_dir / "resources")

            # 渲染图片
            image_bytes = await renderer.render_to_image(HELP_CONFIG, HELP_LIST)

            # 发送图片
            yield event.chain_result([Comp.Image.fromBytes(image_bytes)])
        except Exception as e:
            logger.error(f"生成帮助图片失败: {e}")
            yield event.plain_result(f"❌ 生成帮助图片失败: {str(e)}")
