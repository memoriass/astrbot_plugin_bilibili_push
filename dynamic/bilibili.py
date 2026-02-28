"""Bilibili 动态平台实现"""
import re
import time
from typing import ClassVar, NamedTuple, Any
from httpx import AsyncClient
from yarl import URL
from pydantic import ValidationError

# Core Imports
from ..core.platform import NewMessagePlatform
from ..core.types import Post, RawPost, Target, Category, Tag, ApiError
from ..core.utils import text_similarity, decode_unicode_escapes, wbi_sign
from ..core.compat import type_validate_json
from ..utils.logger import logger

# Model Imports
from ..core.models import (
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
    
    _wbi_keys: tuple[str, str] | None = None
    _wbi_keys_time: float = 0

    async def _get_wbi_keys(self) -> tuple[str, str]:
        if self._wbi_keys and time.time() - self._wbi_keys_time < 3600:
            return self._wbi_keys
        
        client = await self.get_client()
        res = await client.get("https://api.bilibili.com/x/web-interface/nav")
        res_json = res.json()
        if "data" not in res_json or "wbi_img" not in res_json["data"]:
            raise ApiError(f"获取 WBI Keys 失败: {res_json.get('message', '未知错误')}")
            
        data = res_json["data"]["wbi_img"]
        img_url = data["img_url"]
        sub_url = data["sub_url"]
        
        img_key = img_url.split("/")[-1].split(".")[0]
        sub_key = sub_url.split("/")[-1].split(".")[0]
        
        self._wbi_keys = (img_key, sub_key)
        self._wbi_keys_time = time.time()
        return self._wbi_keys

    async def get_target_name(self, target: Target) -> str | None:
        client = await self.get_client()
        # 使用更稳定的 card 接口
        res = await client.get("https://api.bilibili.com/x/web-interface/card", params={"mid": target})
        if res.status_code != 200:
            # Fallback to live master info
            res = await client.get("https://api.live.bilibili.com/live_user/v1/Master/info", params={"uid": target})
            if res.status_code != 200:
                return None
        
        res_data = type_validate_json(UserAPI, res.content)
        if res_data.code != 0:
            return None
            
        if not res_data.data:
            return None
            
        if res_data.data.card:
            return res_data.data.card.name
        if res_data.data.info:
            return res_data.data.info.uname or res_data.data.info.name
        return None

    async def get_sub_list(self, target: Target) -> list[DynRawPost]:
        posts = []
        polymer_failed = False
        
        try:
            posts = await self._get_sub_list_polymer(target)
            if not posts:
                logger.warning(f"Polymer 接口返回为空 {target}, 尝试备用接口...")
                polymer_failed = True
            else:
                from ..core.http import HttpClient
                await HttpClient.set_current_account_status(valid=True, status_code=None)
        except ApiError as e:
            err_msg = str(e)
            if "352" in err_msg or "412" in err_msg or "403" in err_msg:
                from ..core.http import HttpClient
                status_code = 412 if "412" in err_msg else (352 if "352" in err_msg else 403)
                logger.warning(f"检测到 B站 风控 ({err_msg})，正在自动切换账号...")
                await HttpClient.invalidate_current_account(status_code=status_code)
                if await HttpClient.rotate_account():
                    try:
                        posts = await self._get_sub_list_polymer(target)
                        if posts: return posts
                    except: polymer_failed = True
                else:
                    polymer_failed = True
            else:
                logger.warning(f"Polymer 接口失败 ({e})，尝试备用接口...")
                polymer_failed = True
        except Exception as e:
            logger.warning(f"Polymer 接口异常 ({e})，尝试备用接口...")
            polymer_failed = True

        if polymer_failed:
            try:
                posts = await self._get_sub_list_fallback(target)
            except Exception as e2:
                err_msg = str(e2)
                if "412" in err_msg or "403" in err_msg or "352" in err_msg:
                    from ..core.http import HttpClient
                    status_code = 412 if "412" in err_msg else (352 if "352" in err_msg else 403)
                    logger.warning(f"备用接口触发风控 ({status_code})，切换账号并重试...")
                    await HttpClient.invalidate_current_account(status_code=status_code)
                    if await HttpClient.rotate_account():
                         try:
                             posts = await self._get_sub_list_fallback(target)
                             return posts
                         except: pass
                logger.error(f"备用接口抓取也失败了: {e2}")
                posts = []
        
        # Sort by timestamp descending to handle pinned posts (which might be first but old)
        if posts:
            posts.sort(key=lambda x: x.modules.module_author.pub_ts, reverse=True)
            
        return posts

    async def _get_sub_list_polymer(self, target: Target) -> list[DynRawPost]:
        client = await self.get_client()
        # Restore itemOpusStyle to get full Opus data (title/text), otherwise it degrades to empty DrawMajor
        params = {"host_mid": target, "features": "itemOpusStyle"} 
        
        img_key, sub_key = await self._get_wbi_keys()
        signed_params = wbi_sign(params.copy(), img_key, sub_key)
        res = await client.get(
            "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space",
            params=signed_params,
            headers={"Referer": f"https://space.bilibili.com/{target}/dynamic"},
            timeout=10.0,
        )
        if res.status_code == 412:
            raise ApiError("412 Precondition Failed")
        
        res.raise_for_status()
        res_obj = type_validate_json(PostAPI, res.content)
        
        if res_obj.code == 0:
            if (data := res_obj.data) and (items := data.items):
                return [item for item in items if item.type != "DYNAMIC_TYPE_NONE"]
            return []
        elif res_obj.code == -352:
            raise ApiError(f"Risk Control -352")
        else:
            raise ApiError(f"Polymer Code {res_obj.code}")

    async def _get_sub_list_fallback(self, target: Target) -> list[DynRawPost]:
        client = await self.get_client()
        res = await client.get(
            "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/space_history",
            params={"host_uid": target, "offset_dynamic_id": 0, "need_top": 0, "platform": "web"}, # Disable top
            headers={"Referer": f"https://space.bilibili.com/{target}/dynamic"},
            timeout=10.0
        )
        res.raise_for_status()
        data = res.json()
        if data["code"] != 0:
            raise ApiError(f"Fallback Code {data['code']}")

        cards = data.get("data", {}).get("cards", [])
        converted_posts = []
        import json
        for card in cards:
            try:
                desc = card.get("desc", {})
                card_json = json.loads(card.get("card", "{}"))
                post = self._convert_fallback_card(desc, card_json)
                if post:
                    converted_posts.append(post)
            except Exception as e:
                logger.debug(f"Failed to convert fallback card: {e}")
                continue
        return converted_posts

    def _convert_fallback_card(self, desc: dict, card_json: dict) -> DynRawPost | None:
        """Convert old API card to Polymer DynRawPost model"""
        import json

        def get_any(d: dict, *keys):
            for k in keys:
                if "." in k:
                    parts = k.split(".")
                    v = d
                    try:
                        for p in parts:
                            if isinstance(v, dict): v = v.get(p)
                            else: v = None; break
                    except: v = None
                    if v: return v
                elif d.get(k): return d[k]
            return ""

        try:
            # Basic mapping
            type_map = {
                8: "DYNAMIC_TYPE_AV",
                2: "DYNAMIC_TYPE_DRAW", 
                11: "DYNAMIC_TYPE_DRAW", 
                64: "DYNAMIC_TYPE_ARTICLE",
                12: "DYNAMIC_TYPE_ARTICLE", 
                1: "DYNAMIC_TYPE_FORWARD",
                4: "DYNAMIC_TYPE_WORD",
            }
            
            # Type Inference safe-guard
            try:
                raw_type = int(desc.get("type", 0))
            except:
                raw_type = 0

            if raw_type == 0:
                if "aid" in card_json: raw_type = 8
                elif "item" in card_json and "pictures" in card_json["item"]: raw_type = 2
                elif "item" in card_json and "upload_time" in card_json["item"]: raw_type = 4
                
            dyn_type = type_map.get(raw_type, "DYNAMIC_TYPE_WORD") 
            
            # Author
            user_profile = desc.get("user_profile", {}).get("info", {})
            if not user_profile: user_profile = card_json.get("user", {})
            
            author = PostAPI.Modules.Author(
                face=user_profile.get("face", "") or user_profile.get("head_url", ""),
                mid=user_profile.get("uid", 0),
                name=user_profile.get("uname", "") or user_profile.get("name", ""),
                jump_url=f"https://space.bilibili.com/{user_profile.get('uid', 0)}",
                pub_ts=desc.get("timestamp", 0) or get_any(card_json, "item.upload_time", "pubdate", "ctime") or 0,
                type="AUTHOR_TYPE_NORMAL"
            )

            major = None
            text_desc = ""
            orig_item = None
            
            if dyn_type == "DYNAMIC_TYPE_AV":
                major = VideoMajor(
                    type="MAJOR_TYPE_ARCHIVE",
                    archive=VideoMajor.Archive(
                        aid=str(card_json.get("aid", "")),
                        bvid=desc.get("bvid", "") or card_json.get("bvid", ""),
                        title=card_json.get("title", ""),
                        desc=card_json.get("desc", ""),
                        cover=card_json.get("pic", ""),
                        jump_url=f"https://www.bilibili.com/video/{desc.get('bvid', '') or card_json.get('bvid', '')}"
                    )
                )
                text_desc = card_json.get("dynamic", "")
                
            elif dyn_type == "DYNAMIC_TYPE_DRAW":
                items = []
                pics = get_any(card_json, "item.pictures", "item.images", "pics") or []
                for pic in pics:
                    items.append(DrawMajor.Item(width=0, height=0, src=pic.get("img_src", "")))
                    
                major = DrawMajor(
                    type="MAJOR_TYPE_DRAW",
                    # Try to find title (Opus/Album often has title)
                    draw=DrawMajor.Draw(
                        id=0, 
                        items=items,
                        title=get_any(card_json, "item.title", "title")
                    )
                )
                text_desc = get_any(card_json, "item.description", "item.content", "desc")
                
            elif dyn_type == "DYNAMIC_TYPE_WORD":
                text_desc = get_any(card_json, "item.content", "item.description", "dynamic")
                
                # Check for images in word post (upgrade to Draw)
                pics = get_any(card_json, "item.pictures", "item.images", "pics") or []
                if pics:
                    items = []
                    for pic in pics:
                        items.append(DrawMajor.Item(width=0, height=0, src=pic.get("img_src", "")))
                        
                    if items:
                        dyn_type = "DYNAMIC_TYPE_DRAW"
                        major = DrawMajor(
                            type="MAJOR_TYPE_DRAW",
                            draw=DrawMajor.Draw(id=0, items=items)
                        )

            elif dyn_type == "DYNAMIC_TYPE_ARTICLE":
                major = ArticleMajor(
                    type="MAJOR_TYPE_ARTICLE",
                    article=ArticleMajor.Article(
                        id=desc.get("rid", 0),
                        title=card_json.get("title", ""),
                        desc=card_json.get("summary", ""),
                        covers=card_json.get("image_urls", []),
                        jump_url=f"https://www.bilibili.com/read/cv{desc.get('rid', '')}"
                    )
                )
            
            elif dyn_type == "DYNAMIC_TYPE_FORWARD":
                text_desc = get_any(card_json, "item.content", "dynamic", "desc")
                
                import json
                if "origin" in card_json:
                    try:
                        origin_json = json.loads(card_json["origin"])
                        orig_type = card_json.get("item", {}).get("orig_type")
                        if not orig_type:
                            if "aid" in origin_json: orig_type = 8
                            elif "item" in origin_json and "pictures" in origin_json["item"]: orig_type = 2
                        
                        orig_desc = {
                            "type": orig_type,
                            "user_profile": {"info": origin_json.get("user", {})},
                            "timestamp": get_any(origin_json, "item.upload_time", "pubdate", "ctime") or 0,
                            "rid": origin_json.get("rid", ""),
                            "bvid": origin_json.get("bvid", "")
                        }
                        orig_item = self._convert_fallback_card(orig_desc, origin_json)
                    except Exception as e:
                        logger.warning(f"Failed to parse forwarded content: {e}")

            # Fallback for text if empty
            if not text_desc:
                text_desc = get_any(card_json, "dynamic", "desc", "summary", "title", "content") # Last resort

            return PostAPI.Item(
                basic=PostAPI.Basic(rid_str=str(desc.get("rid", ""))),
                id_str=str(desc.get("dynamic_id_str", "")),
                type=dyn_type,
                orig=orig_item,
                modules=PostAPI.Modules(
                    module_author=author,
                    module_dynamic=PostAPI.Modules.Dynamic(
                        major=major,
                        desc=PostAPI.Modules.Desc(text=text_desc, rich_text_nodes=[])
                    )
                )
            )
        except Exception as e:
            logger.warning(f"Convert logic error ({e}) for card: {str(card_json)[:100]}...")
            return None
        except Exception as e:
            logger.warning(f"Convert logic error ({e}) for card: {str(card_json)[:100]}...")
            return None

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
        major = raw_post.modules.module_dynamic.major

        
        if isinstance(major, VideoMajor):
            archive = major.archive
            desc_text = dyn.desc.text if dyn.desc else ""
            parsed = self._text_process(desc_text, archive.desc, archive.title)
            return _ParsedMojarPost(parsed.title, parsed.content, [archive.cover], 
                                  str(URL(archive.jump_url).with_scheme("https")))
        elif isinstance(major, LiveRecommendMajor):
            live_rcmd = major.live_rcmd
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
            text = dyn.desc.text if dyn.desc else ""
            
            # If text is empty, try to get from items description
            if not text:
                item_descs = [item.description for item in major.draw.items if item.description]
                if item_descs:
                    text = "\n".join(item_descs)

            # Use real title if available (Opus), otherwise generate from text
            title = major.draw.title or ""
            if not title and text:
                first_line = text.split("\n")[0]
                title = first_line[:30] + "..." if len(first_line) > 30 else first_line
            
            return _ParsedMojarPost(title, text, 
                                  [item.src for item in major.draw.items], 
                                  f"https://t.bilibili.com/{raw_post.id_str}")
        elif isinstance(major, ArticleMajor):
            return _ParsedMojarPost(major.article.title, major.article.desc, major.article.covers,
                                  str(URL(major.article.jump_url).with_scheme("https")))
        elif isinstance(major, OPUSMajor):
            opus = major.opus
            text = opus.summary.text
            title = opus.title or ""
            if not title and text:
                first_line = text.split("\n")[0]
                title = first_line[:30] + "..." if len(first_line) > 30 else first_line
            
            pics = [pic.url for pic in opus.pics]
            return _ParsedMojarPost(title, text, pics, opus.jump_url)
        
        desc = dyn.desc.text if dyn.desc else ""
        return _ParsedMojarPost("", desc, [], f"https://t.bilibili.com/{raw_post.id_str}")

    async def parse(self, raw_post: DynRawPost) -> Post:
        parsed_raw_post = self.pre_parse_by_mojar(raw_post)
        
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
            id=self.get_id(raw_post),
            type=raw_post.type,
            category=self.get_category(raw_post),
        )
    
    async def fetch_new_post(self, sub_unit) -> list[Post]:
        raw_posts = await self.get_sub_list(sub_unit.sub_target)
        posts = []
        for rp in raw_posts:
            posts.append(await self.parse(rp))
        return posts
