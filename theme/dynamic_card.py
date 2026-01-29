from pathlib import Path
import markdown
from . import Theme
from ..core.types import Post, MsgImage, MessageSegment
from .renderer import render_template

class DynamicCardTheme(Theme):
    async def render(self, post: Post) -> list[MessageSegment]:
        template_path = Path(__file__).parent / "templates"
        
        md_lines = []
        if post.title:
            md_lines.append(f"## {post.title}")
            
        if post.repost:
            md_lines.append(f"> 转发 @{post.repost.nickname}:")
            if post.repost.title:
                md_lines.append(f"> **{post.repost.title}**")
            md_lines.append(f"> {post.repost.content}")
            for img in post.repost.images:
                md_lines.append(f"> ![]({img})")
            md_lines.append("\n---")
            
        if post.content:
            md_lines.append(post.content)
            
        for img in post.images:
            md_lines.append(f"![]({img})")
            
        html_content = markdown.markdown("\n\n".join(md_lines))
        
        img_bytes = await render_template(
            template_path=template_path,
            template_name="dynamic_card.html.jinja",
            templates={"content_html": html_content}
        )
        
        return [MsgImage(data=img_bytes)]
