import re
import time
from typing import Optional, Dict, Any
from .http import HttpClient
from ..logger import logger

class BilibiliParser:
    # Regexes
    BV_PATTERN = re.compile(r"(BV[0-9a-zA-Z]{10})")
    AV_PATTERN = re.compile(r"av(\d+)")
    DYNAMIC_PATTERN = re.compile(r"(?:t\.bilibili\.com|bilibili\.com/dynamic)/(\d+)")
    OPUS_PATTERN = re.compile(r"bilibili\.com/opus/(\d+)")
    LIVE_PATTERN = re.compile(r"live\.bilibili\.com/(\d+)")
    SHORT_LINK_PATTERN = re.compile(r"(b23\.tv/[A-Za-z\d]+)")

    def __init__(self):
        pass

    async def parse_message(self, text: str) -> Optional[Dict[str, Any]]:
        # 1. Short link redirect
        if m := self.SHORT_LINK_PATTERN.search(text):
            url = f"https://{m.group(1)}"
            try:
                client = await HttpClient.get_client()
                # Use follow_redirects=True to get final URL
                res = await client.head(url, follow_redirects=True, timeout=5.0)
                text = str(res.url)
            except Exception as e:
                logger.debug(f"Follow short link failed: {e}")

        # 2. Match patterns
        if m := self.BV_PATTERN.search(text):
            return await self.get_video_info(bvid=m.group(1))
        if m := self.AV_PATTERN.search(text):
            return await self.get_video_info(avid=m.group(1))
        if m := self.DYNAMIC_PATTERN.search(text) or self.OPUS_PATTERN.search(text):
            return await self.get_dynamic_info(m.group(1))
        if m := self.LIVE_PATTERN.search(text):
            return await self.get_live_info(m.group(1))
        
        return None

    async def get_video_info(self, bvid: str = None, avid: str = None) -> Optional[Dict[str, Any]]:
        client = await HttpClient.get_client()
        params = {}
        if bvid: params["bvid"] = bvid
        else: params["aid"] = avid
        
        try:
            res = await client.get("https://api.bilibili.com/x/web-interface/view", params=params)
            data = res.json()
            if data["code"] == 0:
                v = data["data"]
                return {
                    "type": "video",
                    "title": v["title"],
                    "description": v["desc"],
                    "cover": v["pic"],
                    "duration": self._format_duration(v["duration"]),
                    "nickname": v["owner"]["name"],
                    "avatar": v["owner"]["face"],
                    "pub_time": time.strftime("%Y-%m-%d %H:%M", time.localtime(v["pubdate"])),
                    "stats": {
                        "view": self._format_count(v["stat"]["view"]),
                        "like": self._format_count(v["stat"]["like"]),
                        "coin": self._format_count(v["stat"]["coin"]),
                    }
                }
        except Exception as e:
            logger.error(f"Parse video failed: {e}")
        return None

    async def get_dynamic_info(self, dynamic_id: str) -> Optional[Dict[str, Any]]:
        client = await HttpClient.get_client()
        try:
            res = await client.get(
                "https://api.bilibili.com/x/polymer/web-dynamic/v1/detail",
                params={"id": dynamic_id}
            )
            data = res.json()
            if data["code"] == 0:
                item = data["data"]["item"]
                modules = item["modules"]
                author = modules["module_author"]
                dyn = modules["module_dynamic"]
                
                content = dyn["desc"]["text"]
                pics = []
                major = dyn.get("major")
                title = ""
                
                if major:
                    if major["type"] == "MAJOR_TYPE_DRAW":
                        pics = [p["src"] for p in major["draw"]["items"]]
                    elif major["type"] == "MAJOR_TYPE_ARCHIVE":
                        archive = major["archive"]
                        title = archive["title"]
                        content = archive["desc"]
                        pics = [archive["cover"]]
                    elif major["type"] == "MAJOR_TYPE_OPUS":
                        opus = major["opus"]
                        title = opus.get("title", "")
                        content = opus["summary"]["text"]
                        pics = [p["url"] for p in opus.get("pics", [])]

                cover = pics[0] if pics else ""
                
                return {
                    "type": "dynamic",
                    "title": title,
                    "description": content,
                    "cover": cover,
                    "nickname": author["name"],
                    "avatar": author["face"],
                    "pub_time": author["pub_time"],
                }
        except Exception as e:
            logger.error(f"Parse dynamic failed: {e}")
        return None

    async def get_live_info(self, room_id: str) -> Optional[Dict[str, Any]]:
        client = await HttpClient.get_client()
        try:
            res = await client.get("https://api.live.bilibili.com/room/v1/Room/get_info", params={"room_id": room_id})
            data = res.json()
            if data["code"] == 0:
                r = data["data"]
                res_u = await client.get("https://api.live.bilibili.com/live_user/v1/Master/info", params={"uid": r["uid"]})
                data_u = res_u.json()
                nickname = data_u["data"]["info"]["uname"] if data_u["code"] == 0 else "未知主播"
                avatar = data_u["data"]["info"]["face"] if data_u["code"] == 0 else ""

                return {
                    "type": "live",
                    "title": r["title"],
                    "description": f"直播间ID: {room_id}",
                    "cover": r["user_cover"] or r["cover"],
                    "nickname": nickname,
                    "avatar": avatar,
                    "pub_time": "正在直播" if r["live_status"] == 1 else "未开播",
                }
        except Exception as e:
            logger.error(f"Parse live failed: {e}")
        return None

    def _format_duration(self, seconds: int) -> str:
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h > 0: return f"{h:d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _format_count(self, count: int) -> str:
        if count >= 10000:
            return f"{count / 10000:.1f}万"
        return str(count)
