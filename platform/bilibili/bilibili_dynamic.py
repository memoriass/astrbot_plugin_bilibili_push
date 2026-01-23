"""Bilibili 动态平台实现"""
import re
from typing import ClassVar, NamedTuple, Any
from httpx import AsyncClient
from yarl import URL
from pydantic import ValidationError

# Core Imports
from ...core.platform import NewMessagePlatform
from ...core.types import Post, RawPost, Target, Category, Tag, ApiError
from ...core.utils import text_similarity, decode_unicode_escapes
from ...core.compat import type_validate_json
from ...logger import logger

# Model Imports
from .models import (
    ArticleMajor, CommonMajor, CoursesMajor, DeletedMajor, DrawMajor,
    DynamicType, DynRawPost, LiveMajor, LiveRecommendMajor, OPUSMajor,
    PGCMajor, PostAPI, UnknownMajor, UserAPI, VideoMajor
)

class _ProcessedText(NamedTuple):
    title: str
    content: str

class _ParsedMojarPost(NamedTuple):
    title: str
    content: str
    pics: list[str]
    url: str | None = None

class BilibiliDynamic(NewMessagePlatform):
    platform_name = "bilibili"
    name = "B站"
    categories: ClassVar[dict[Category, str]] = {
        1: "一般动态",
        2: "专栏文章",
        3: "视频",
        4: "纯文字",
        5: "转发",
        6: "直播推送",
    }
    
    async def get_target_name(self, target: Target) -> str | None:
        client = await self.get_client()
        res = await client.get("https://api.live.bilibili.com/live_user/v1/Master/info", params={"uid": target})
        if res.status_code != 200:
            return None
        res_data = type_validate_json(UserAPI, res.content)
        if res_data.code != 0:
            return None
        return res_data.data.info.uname if res_data.data else None

    async def get_sub_list(self, target: Target) -> list[DynRawPost]:
        client = await self.get_client()
        params = {"host_mid": target, "timezone_offset": -480, "offset": "", "features": "itemOpusStyle"}
        try:
            res = await client.get(
                "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space",
                params=params,
                timeout=10.0,
            )
            res.raise_for_status()
            res_obj = type_validate_json(PostAPI, res.content)
            
            if res_obj.code == 0:
                if (data := res_obj.data) and (items := data.items):
                    # 过滤已删除的动态
                    return [item for item in items if item.type != "DYNAMIC_TYPE_NONE"]
                return []
            elif res_obj.code == -352:
                # 简单处理风控，不重试
                logger.warning(f"Bilibili API 352 风控: {target}")
                raise ApiError(res.request.url.path)
            else:
                raise ApiError(f"API Code {res_obj.code}")
        except Exception as e:
            logger.error(f"获取动态列表失败: {e}")
            raise

    def get_id(self, post: DynRawPost) -> str:
        return post.id_str or str(post.basic.rid_str)

    def get_date(self, post: DynRawPost) -> int:
        return post.modules.module_author.pub_ts

    def _do_get_category(self, post_type: DynamicType) -> Category:
        match post_type:
            case "DYNAMIC_TYPE_DRAW" | "DYNAMIC_TYPE_COMMON_VERTICAL" | "DYNAMIC_TYPE_COMMON_SQUARE":
                return Category(1)
            case "DYNAMIC_TYPE_ARTICLE":
                return Category(2)
            case "DYNAMIC_TYPE_AV":
                return Category(3)
            case "DYNAMIC_TYPE_WORD":
                return Category(4)
            case "DYNAMIC_TYPE_FORWARD":
                return Category(5)
            case "DYNAMIC_TYPE_LIVE_RCMD" | "DYNAMIC_TYPE_LIVE":
                return Category(6)
            case _:
                return Category(99) # Unknown

    def get_category(self, post: DynRawPost) -> Category:
        return self._do_get_category(post.type)

    def get_tags(self, raw_post: DynRawPost) -> list[Tag]:
        tags: list[Tag] = []
        if raw_post.topic:
            tags.append(raw_post.topic.name)
        if desc := raw_post.modules.module_dynamic.desc:
            for node in desc.rich_text_nodes:
                if node.get("type") == "RICH_TEXT_NODE_TYPE_TOPIC":
                    tags.append(node["text"].strip("#"))
        return tags

    # ... _text_process 和 pre_parse_by_mojar 逻辑较长，直接硬编码在这里 ...
    def _text_process(self, dynamic: str, desc: str, title: str) -> _ProcessedText:
        title_similarity = 0.0 if len(title) == 0 or len(desc) == 0 else text_similarity(title, desc[: len(title)])
        if title_similarity > 0.9:
            desc = desc[len(title) :].lstrip()
        content_similarity = 0.0 if len(dynamic) == 0 or len(desc) == 0 else text_similarity(dynamic, desc)
        if content_similarity > 0.8:
            return _ProcessedText(title, desc if len(dynamic) < len(desc) else dynamic)
        else:
            return _ProcessedText(title, f"{desc}" + (f"\n=================\n{dynamic}" if dynamic else ""))

    def pre_parse_by_mojar(self, raw_post: DynRawPost) -> _ParsedMojarPost:
        dyn = raw_post.modules.module_dynamic
        # 简化匹配逻辑，复用原版结构
        major = raw_post.modules.module_dynamic.major
        
        if isinstance(major, VideoMajor):
            archive = major.archive
            desc_text = dyn.desc.text if dyn.desc else ""
            parsed = self._text_process(desc_text, archive.desc, archive.title)
            return _ParsedMojarPost(parsed.title, parsed.content, [archive.cover], 
                                  str(URL(archive.jump_url).with_scheme("https")))
        elif isinstance(major, LiveRecommendMajor):
            live_rcmd = major.live_rcmd
            # LiveRecommend content is a JSON string
            content_data = type_validate_json(LiveRecommendMajor.Content, live_rcmd.content)
            live_info = content_data.live_play_info
            return _ParsedMojarPost(
                live_info.title,
                f"{live_info.parent_area_name} {live_info.area_name}",
                [live_info.cover],
                str(URL(live_info.link).with_scheme("https").with_query(None))
            )
        elif isinstance(major, LiveMajor):
            live = major.live
            return _ParsedMojarPost(
                live.title,
                f"{live.desc_first}\n{live.desc_second}",
                [live.cover],
                str(URL(live.jump_url).with_scheme("https"))
            )
        elif isinstance(major, DrawMajor):
            return _ParsedMojarPost("", dyn.desc.text if dyn.desc else "", 
                                  [item.src for item in major.draw.items], 
                                  f"https://t.bilibili.com/{raw_post.id_str}")
        elif isinstance(major, ArticleMajor):
            return _ParsedMojarPost(major.article.title, major.article.desc, major.article.covers,
                                  str(URL(major.article.jump_url).with_scheme("https")))
        # ... 其他类型简化处理，默认 fallback
        
        desc = dyn.desc.text if dyn.desc else ""
        return _ParsedMojarPost("", desc, [], f"https://t.bilibili.com/{raw_post.id_str}")

    async def parse(self, raw_post: DynRawPost) -> Post:
        parsed_raw_post = self.pre_parse_by_mojar(raw_post)
        
        # 处理转发
        repost = None
        if self.get_category(raw_post) == Category(5) and raw_post.orig:
            if isinstance(raw_post.orig, PostAPI.Item):
                parsed_repost = self.pre_parse_by_mojar(raw_post.orig)
                repost = Post(
                    platform=self.platform_name,
                    content=parsed_repost.content,
                    title=parsed_repost.title,
                    images=list(parsed_repost.pics),
                    timestamp=self.get_date(raw_post.orig),
                    url=parsed_repost.url or "",
                    nickname=raw_post.orig.modules.module_author.name,
                    avatar=raw_post.orig.modules.module_author.face,
                    id=self.get_id(raw_post.orig),
                )

        return Post(
            platform=self.platform_name,
            content=parsed_raw_post.content,
            title=parsed_raw_post.title,
            images=list(parsed_raw_post.pics),
            timestamp=self.get_date(raw_post),
            url=parsed_raw_post.url or "",
            nickname=raw_post.modules.module_author.name,
            avatar=raw_post.modules.module_author.face,
            repost=repost,
            id=self.get_id(raw_post),
        )
    
    # 简单的 fetch 实现，调用 get_sub_list
    async def fetch_new_post(self, sub_unit) -> list[Post]:
        # 这里需要实现 filter 逻辑 (原版 NewMessage.fetch_new_post)
        # 但我们简化：直接获取，由 Scheduler 根据 ID 去重
        raw_posts = await self.get_sub_list(sub_unit.sub_target)
        posts = []
        for rp in raw_posts:
            # 过滤 Tags 和 Category (暂略，如果需要可以搬运 filter_user_custom)
            posts.append(await self.parse(rp))
        return posts
