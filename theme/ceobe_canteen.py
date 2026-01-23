from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

from ..core.types import Post, MessageSegment, MsgText, MsgImage
from . import Theme
from .renderer import render_template

@dataclass
class CeobeInfo:
    datasource: str
    time: str

@dataclass
class CeobeContent:
    text: str
    image: str | None = None

@dataclass
class CeobeRetweet:
    author: str
    content: str | None
    image: str | None

@dataclass
class CeobeCard:
    info: CeobeInfo
    content: CeobeContent
    retweet: CeobeRetweet | None
    qr: str | None = None

class CeobeCanteenTheme(Theme):
    template_path = Path(__file__).parent / "templates"
    
    async def render(self, post: Post) -> list[MessageSegment]:
        # 1. 构造 View Model
        info = CeobeInfo(
            datasource=post.nickname or "Bilibili",
            time=datetime.fromtimestamp(post.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        )
        
        # 处理图片 (取第一张)
        main_image = None
        if post.images:
            if isinstance(post.images[0], str):
                main_image = post.images[0]
            # TODO: Handle bytes/Path images
            
        content = CeobeContent(text=post.content, image=main_image)
        
        retweet = None
        if post.repost:
            repost_img = None
            if post.repost.images and isinstance(post.repost.images[0], str):
                repost_img = post.repost.images[0]
            
            repost_author = f"@{post.repost.nickname}:" if post.repost.nickname else ""
            retweet = CeobeRetweet(
                author=repost_author,
                content=post.repost.content,
                image=repost_img
            )
            
        # 2. 渲染
        # 注意: 模板需要 bison_logo 和 ceobe_logo base64
        # 这里为了演示简单，我们先传None，或者需要读取文件转base64
        # 模板可能需要修改以支持 url 而不是 base64，或者 Playwright 无法加载本地文件
        
        card = CeobeCard(info=info, content=content, retweet=retweet)
        
        # 这里需要读取logo并转base64，暂略，假设模板能处理缺失
        try:
            img_bytes = await render_template(
                self.template_path,
                "ceobe_canteen.html.jinja",
                {
                    "card": card,
                    "bison_logo": "", # TODO
                    "ceobe_logo": "", # TODO
                },
                viewport={"width": 600, "height": 800},
                selector="#ceobecanteen-card"
            )
            
            msgs = [MsgImage(img_bytes)]
        except Exception as e:
            # Fallback
            return [MsgText(f"渲染失败: {e}\n{post.title}")]

        # 构造文本部分
        text = f"来源: {post.platform} {post.nickname or ''}\n"
        if post.url:
            text += f"详情: {post.url}"
        msgs.append(MsgText(text))
        
        return msgs
