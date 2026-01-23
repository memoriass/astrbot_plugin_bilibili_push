from ..core.types import Post, MessageSegment, MsgText, MsgImage
from . import Theme

class BriefTheme(Theme):
    async def render(self, post: Post) -> list[MessageSegment]:
        text = f"{post.title}\n\n"
        text += f"来源: {post.platform} {post.nickname or ''}{' 的转发' if post.repost else ''}\n"
        
        urls = []
        if post.repost and post.repost.url:
            urls.append(f"转发详情: {post.repost.url}")
        if post.url:
            urls.append(f"详情: {post.url}")
            
        if urls:
            text += "\n".join(urls)
            
        msgs = [MsgText(text)]
        
        # 只取第一张图
        if post.images:
            msgs.append(MsgImage(post.images[0]))
            
        return msgs
