from pathlib import Path
import markdown
from . import Theme
from ..core.types import Post, MsgImage, MessageSegment
from .renderer import render_template

class MovieCardTheme(Theme):
    async def render(self, post: Post) -> list[MessageSegment]:
        template_path = Path(__file__).parent / "templates"
        
        # 准备数据
        # 封面图：优先取文章/视频封面，如果没有则用第一张配图，再没有用头像
        cover = ""
        if post.images:
            cover = post.images[0]
        elif post.repost and post.repost.images:
            cover = post.repost.images[0]
        else:
            cover = post.avatar or ""

        # 构建 Markdown 内容用于提取摘要（这里简单处理，直接传文本给模板）
        # 实际模板中可能只需要纯文本摘要
        
        # 格式化日期
        import datetime
        dt = datetime.datetime.fromtimestamp(post.timestamp)
        date_str = dt.strftime("%Y-%m-%d %H:%M:%S")

        # 渲染
        img_bytes = await render_template(
            template_path=template_path,
            template_name="movie_card.html.jinja",
            templates={
                "post": post,
                "cover": cover,
                "date_str": date_str,
            },
            selector=".movie-card"
        )
        
        return [MsgImage(data=img_bytes)]
