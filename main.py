"""Bilibili 推送插件主入口 (Core重构版)"""

import asyncio
import io
import time
from pathlib import Path

import qrcode

import astrbot.api.message_components as Comp
from astrbot.api import AstrBotConfig
from astrbot.api import logger as astrbot_logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from .core.http import HttpClient
from .core.parser import BilibiliParser
from .core.types import MsgImage, MsgText
from .scheduler import BilibiliScheduler
from .sub_manager import DBManager, Subscription
from .theme.renderer import render_template


@register(
    "astrbot_plugin_bilibili_push", "Aisidaka", "Bilibili 动态与直播推送插件", "1.0.0"
)
class Main(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config or {}

        self.platform_name = self.config.get("platform_name", "auto")
        self.check_interval = self.config.get("check_interval", 30)

        self.data_dir = (
            Path(get_astrbot_data_path())
            / "plugin_data"
            / "astrbot_plugin_bilibili_push"
        )

        # Initialize directories
        self.temp_dir = self.data_dir / "temp"
        self.bg_dir = self.data_dir / "backgrounds"

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.bg_dir.mkdir(parents=True, exist_ok=True)

        self.db = DBManager(self.data_dir)
        self.scheduler = BilibiliScheduler(
            db=self.db,
            check_interval=self.check_interval,
            push_on_startup=self.config.get("push_on_startup", False),
            render_type=self.config.get("render_type", "image"),
            image_template=self.config.get("image_template", "dynamic_card"),
            on_new_post=self.on_new_post,
            star=self,
        )

        self.temp_cleanup_days = self.config.get("temp_cleanup_days", 1)
        self.search_cache_expiry_hours = self.config.get("search_cache_expiry_hours", 24)
        self.enable_link_parser = self.config.get("enable_link_parser", True)
        self.parser = BilibiliParser()

    async def initialize(self):
        await HttpClient.set_star_instance(self)
        await self.scheduler.start()
        asyncio.create_task(self._cleanup_temp_files())

    async def terminate(self):
        await self.scheduler.stop()
        await HttpClient.close()

    async def on_new_post(self, platform_name: str, target_id: str, msgs: list):
        try:
            chain_parts = []
            for msg in msgs:
                if isinstance(msg, MsgText):
                    chain_parts.append(Comp.Plain(msg.text))
                elif isinstance(msg, MsgImage):
                    data = msg.data
                    if isinstance(data, bytes):
                        temp_file = (
                            self.temp_dir / f"temp_{int(time.time() * 1000)}.jpg"
                        )
                        with open(temp_file, "wb") as f:
                            f.write(data)
                        chain_parts.append(
                            Comp.Image.fromFileSystem(str(temp_file.absolute()))
                        )
                    elif isinstance(data, (str, Path)):
                        s_data = str(data)
                        if s_data.startswith("http"):
                            chain_parts.append(Comp.Image.fromURL(s_data))
                        else:
                            chain_parts.append(Comp.Image.fromFileSystem(s_data))

            platform = self.get_effective_platform_name()
            if target_id.startswith(f"{platform}:"):
                origin = target_id
            elif ":" in target_id:
                origin = f"{platform}:{target_id}"
            else:
                group_id = (
                    target_id.replace(":", "_") if ":" in target_id else target_id
                )
                origin = f"{platform}:GroupMessage:{group_id}"

            chain = MessageChain(chain_parts)
            await self.context.send_message(origin, chain)
            astrbot_logger.info(f"推送消息成功 -> {origin}")

        except Exception as e:
            astrbot_logger.error(f"消息发送失败: {e}", exc_info=True)

    def _get_target_id(self, event: AstrMessageEvent) -> str | None:
        """从事件中提取目标ID (类型:ID)"""
        return f"{event.message_obj.type.value}:{event.session_id}"

    async def _get_bili_user_info(self, uid: str):
        client = await HttpClient.get_client()
        try:
            res = await client.get(
                "https://api.bilibili.com/x/web-interface/card",
                params={"mid": uid},
                timeout=5,
            )
            if res.status_code == 200:
                data = res.json()
                if data["code"] == 0:
                    card = data["data"]["card"]
                    return {
                        "username": card["name"],
                        "face": card["face"],
                        "uid": uid
                    }
        except Exception as e:
            astrbot_logger.warning(f"Fetch user info failed for {uid}: {e}")
        return None

    async def _cleanup_temp_files(self):
        """清理过期的临时文件"""
        try:
            now = time.time()
            cutoff = now - (self.temp_cleanup_days * 86400)
            count = 0
            for f in self.temp_dir.iterdir():
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink()
                    count += 1
            if count > 0:
                astrbot_logger.info(f"Cleaned up {count} temporary files.")
        except Exception as e:
            astrbot_logger.error(f"Cleanup temp files failed: {e}")

    async def _get_background_uri(self) -> dict:
        """获取并压缩随机背景图 URI"""
        import base64
        import mimetypes
        import random
        try:
            from PIL import Image
        except ImportError:
            return ""

        bg_files = [
            f
            for f in self.bg_dir.iterdir()
            if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
        ]

        if not bg_files:
            return ""

        bg_file = random.choice(bg_files)
        try:
            with Image.open(bg_file) as img:
                # 进一步压缩以提升渲染速度
                target_width = 1000
                if img.width > target_width:
                    ratio = target_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((target_width, new_height), Image.Resampling.LANCZOS)
                
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                buffer = io.BytesIO()
                # 降低质量以换取速度，背景图不需要太清晰
                img.save(buffer, format="JPEG", quality=40)
                base64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
                return {
                    "uri": f"data:image/jpeg;base64,{base64_str}",
                    "width": img.width,
                    "height": img.height
                }
        except Exception as e:
            astrbot_logger.error(f"Generate background URI failed: {e}")
            try:
                mime_type, _ = mimetypes.guess_type(bg_file)
                from PIL import Image
                with Image.open(bg_file) as img:
                    w, h = img.size
                with open(bg_file, "rb") as f:
                    return {
                        "uri": f"data:{mime_type or 'image/jpeg'};base64,{base64.b64encode(f.read()).decode('utf-8')}",
                        "width": w,
                        "height": h
                    }
            except:
                return {"uri": "", "width": 1400, "height": 1000}
        return {"uri": "", "width": 1400, "height": 1000}

    @filter.command("添加b站订阅", alias={"bilibili 添加订阅", "add_bili_sub"})
    async def add_subscription(self, event: AstrMessageEvent, uid: str):
        target_id = self._get_target_id(event)
        if not target_id:
            yield event.plain_result("❌ 无法获取会话 ID")
            return

        try:
            user_info = await self._get_bili_user_info(uid)
            if not user_info:
                yield event.plain_result(f"❌ 无法获取 UP 主信息: {uid}。")
                return
            
            username = user_info["username"]
            face = user_info["face"]

            sub = Subscription(
                uid=uid,
                username=username,
                sub_type="dynamic",
                categories=[1, 2, 3, 4, 5, 6],
                tags=[],
                target_id=target_id,
                enabled=True,
            )

            if self.db.add_subscription(sub):
                # Render visual confirmation
                template_path = Path(__file__).parent / "theme" / "templates"
                bg_data = await self._get_background_uri()
                msg = f"✅ 已添加动态订阅: {username} ({uid})"
                
                img_bytes = await render_template(
                    template_path,
                    "sub_add.html.jinja",
                    {
                        "username": username,
                        "face": face,
                        "uid": uid,
                        "sub_type": "dynamic",
                        "bg_image_uri": bg_data["uri"],
                        "action": "ADDED"
                    },
                    viewport={"width": 400, "height": 400},
                )
                yield event.chain_result([
                    Comp.Plain(msg),
                    Comp.Image.fromBytes(img_bytes)
                ])
            else:
                yield event.plain_result("⚠️ 订阅已存在")
        except Exception as e:
            astrbot_logger.error(f"添加失败: {e}")
            yield event.plain_result(f"❌ 内部错误: {e}")

    @filter.command("添加b站直播", alias={"bilibili 添加直播", "add_bili_live"})
    async def add_live_subscription(self, event: AstrMessageEvent, uid: str):
        target_id = self._get_target_id(event)
        if not target_id:
            yield event.plain_result("❌ 无法获取会话 ID")
            return

        try:
            user_info = await self._get_bili_user_info(uid)
            if not user_info:
                yield event.plain_result(f"❌ 无法获取 UP 主信息: {uid}。")
                return
            
            username = user_info["username"]
            face = user_info["face"]

            sub = Subscription(
                uid=uid,
                username=username,
                sub_type="live",
                categories=[1, 2, 3],
                tags=[],
                target_id=target_id,
                enabled=True,
            )
            if self.db.add_subscription(sub):
                # Render visual confirmation
                template_path = Path(__file__).parent / "theme" / "templates"
                bg_data = await self._get_background_uri()
                msg = f"✅ 已添加直播订阅: {username} ({uid})"
                
                img_bytes = await render_template(
                    template_path,
                    "sub_add.html.jinja",
                    {
                        "username": username,
                        "face": face,
                        "uid": uid,
                        "sub_type": "live",
                        "bg_image_uri": bg_data["uri"],
                        "action": "ADDED"
                    },
                    viewport={"width": 400, "height": 400},
                )
                yield event.chain_result([
                    Comp.Plain(msg),
                    Comp.Image.fromBytes(img_bytes)
                ])
            else:
                yield event.plain_result("⚠️ 订阅已存在")
        except Exception as e:
            yield event.plain_result(f"❌ 添加失败: {e}")

    @filter.command(
        "取消b站订阅", alias={"删除b站订阅", "bilibili 删除订阅", "del_bili_sub"}
    )
    async def remove_subscription_cmd(self, event: AstrMessageEvent, uid: str):
        """取消动态订阅"""
        target_id = self._get_target_id(event)
        if not target_id:
            return

        user_info = await self._get_bili_user_info(uid)
        username = user_info["username"] if user_info else uid
        face = user_info["face"] if user_info else "http://i0.hdslb.com/bfs/face/member/noface.jpg"

        if self.db.remove_subscription(uid, "dynamic", target_id):
            # Render visual confirmation
            template_path = Path(__file__).parent / "theme" / "templates"
            bg_data = await self._get_background_uri()
            msg = f"🗑️ 已取消动态订阅: {username} ({uid})"
            
            img_bytes = await render_template(
                template_path,
                "sub_add.html.jinja",
                {
                    "username": username,
                    "face": face,
                    "uid": uid,
                    "sub_type": "dynamic",
                    "bg_image_uri": bg_data["uri"],
                    "action": "REMOVED"
                },
                viewport={"width": 400, "height": 400},
            )
            yield event.chain_result([
                Comp.Plain(msg),
                Comp.Image.fromBytes(img_bytes)
            ])
        else:
            yield event.plain_result(f"❌ 动态订阅不存在: {uid}")

    @filter.command(
        "取消b站直播", alias={"删除b站直播", "bilibili 删除直播", "del_bili_live"}
    )
    async def remove_live_subscription_cmd(self, event: AstrMessageEvent, uid: str):
        """取消直播订阅"""
        target_id = self._get_target_id(event)
        if not target_id:
            return

        user_info = await self._get_bili_user_info(uid)
        username = user_info["username"] if user_info else uid
        face = user_info["face"] if user_info else "http://i0.hdslb.com/bfs/face/member/noface.jpg"

        if self.db.remove_subscription(uid, "live", target_id):
            # Render visual confirmation
            template_path = Path(__file__).parent / "theme" / "templates"
            bg_data = await self._get_background_uri()
            msg = f"🗑️ 已取消直播订阅: {username} ({uid})"
            
            img_bytes = await render_template(
                template_path,
                "sub_add.html.jinja",
                {
                    "username": username,
                    "face": face,
                    "uid": uid,
                    "sub_type": "live",
                    "bg_image_uri": bg_data["uri"],
                    "action": "REMOVED"
                },
                viewport={"width": 400, "height": 400},
            )
            yield event.chain_result([
                Comp.Plain(msg),
                Comp.Image.fromBytes(img_bytes)
            ])
        else:
            yield event.plain_result(f"❌ 直播订阅不存在: {uid}")

    @filter.command("b站登录", alias={"bilibili 登录", "b站扫码"})
    async def bilibili_login(self, event: AstrMessageEvent):
        """B站扫码登录以获取 Buvid 和 SESSDATA"""
        client = await HttpClient.get_client()

        try:
            # 使用更稳定的 passport 域名
            res = await client.get(
                "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
            )
            data = res.json()["data"]
            url = data["url"]
            qrcode_key = data["qrcode_key"]
        except Exception as e:
            yield event.plain_result(f"❌ 获取登录二维码失败: {e}")
            return

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format="PNG")
        img_bytes = img_byte_arr.getvalue()

        qr_path = self.temp_dir / f"qr_{int(time.time())}.png"
        with open(qr_path, "wb") as f:
            f.write(img_bytes)

        yield event.chain_result(
            [
                Comp.Plain("请使用 B站 App 扫码登录：\n"),
                Comp.Image.fromFileSystem(str(qr_path.absolute())),
            ]
        )

        max_retries = 30
        for _ in range(max_retries):
            await asyncio.sleep(4)
            try:
                check_res = await client.get(
                    "https://passport.bilibili.com/x/passport-login/web/qrcode/poll",
                    params={"qrcode_key": qrcode_key},
                )
                check_data = check_res.json()["data"]
                code = check_data["code"]

                if code == 0:
                    # 获取最新 Response 中的 Set-Cookie
                    new_cookies = dict(check_res.cookies)
                    
                    # 优先从 cookie 获取 UID (DedeUserID)
                    uid = new_cookies.get("DedeUserID")
                    if not uid and check_data.get("mid"):
                        uid = str(check_data.get("mid"))
                    
                    # 使用新 Cookie 调用 nav 接口获取完整的用户信息 (uname/face)
                    try:
                        nav_res = await client.get("https://api.bilibili.com/x/web-interface/nav", cookies=new_cookies, timeout=5)
                        nav_data = nav_res.json()
                        if nav_data["code"] == 0:
                            n = nav_data["data"]
                            uid = str(n.get("mid") or uid)
                            uname = n.get("uname", "未知用户")
                            face = n.get("face", "")
                        else:
                            uname = check_data.get("uname", "未知用户")
                            face = check_data.get("face", "")
                    except Exception as e:
                        astrbot_logger.warning(f"Fetch nav info after login failed: {e}")
                        uname = check_data.get("uname", "未知用户")
                        face = check_data.get("face", "")

                    # Persist via new Account Pool logic
                    await HttpClient.add_account(
                        uid=str(uid),
                        name=str(uname),
                        face=str(face),
                        cookies=new_cookies,
                    )

                    yield event.plain_result(
                        f"✅ 登录成功！已添加账号：{uname} (UID: {uid})"
                    )
                    return
                elif code == 86038:
                    yield event.plain_result("❌ 二维码已失效，请重新输入指令登录。")
                    return
                elif code == 86101 or code == 86090:
                    pass
            except Exception as e:
                astrbot_logger.error(f"轮询登录状态出错: {e}")

        yield event.plain_result("⏰ 登录超时，请重新输入指令。")

    @filter.command("b站登录状态")
    async def login_status(self, event: AstrMessageEvent):
        # List all accounts
        accounts = await HttpClient.get_accounts()

        if not accounts:
            yield event.plain_result("❌ 当前未登录任何账号")
            return

        # Prepare data for template
        display_list = []
        for acc in accounts:
            display_list.append(
                {
                    "uid": acc.get("uid"),
                    "username": acc.get("name"),
                    "face": acc.get("face")
                    or "http://i0.hdslb.com/bfs/face/member/noface.jpg",
                    # Using template flags
                    "is_login_profile": True,  # Hides normal tags
                    # Show status via dot?
                    # We can hack `has_live` + `is_live` to show green/grey dot for Valid/Invalid
                    "has_live": True,
                    "is_live": acc.get("valid", True),
                    "has_dynamic": False,
                }
            )

        bg_data = await self._get_background_uri()

        # Render
        # Render using sub_list template
        template_path = Path(__file__).parent / "theme" / "templates"
        
        img_bytes = await render_template(
            template_path,
            "sub_list.html.jinja",
            {
                "subs": display_list, 
                "bg_image_uri": bg_data["uri"],
                "page_title": "登录状态"
            },
            viewport={"width": bg_data["width"], "height": 10}, # Height will auto-expand
            selector="body",
        )
        yield event.chain_result([Comp.Image.fromBytes(img_bytes)])

        
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def handle_bilibili_links(self, event: AstrMessageEvent):
        """自动解析消息中的 B站 链接"""
        if not self.enable_link_parser:
            return
            
        # 如果消息是指令，跳过解析以避免重复操作
        if event.message_str.startswith("/"):
            return

        info = await self.parser.parse_message(event.message_str)
        if not info:
            return

        # Render
        template_path = Path(__file__).parent / "theme" / "templates"
        try:
            img_bytes = await render_template(
                template_path,
                "parser_bili.html.jinja",
                info,
                viewport={"width": 640, "height": 800},
                selector=".card"
            )
            yield event.chain_result([Comp.Image.fromBytes(img_bytes)])
        except Exception as e:
            astrbot_logger.error(f"Render parsed link failed: {e}")

    @filter.command("b站搜索", alias={"bilibili 搜索", "search_bili"})
    async def bilibili_search(self, event: AstrMessageEvent, keyword: str):
        """b站搜索 xxx"""
        # 1. Check Cache
        cache_key = f"search_cache_{keyword}"
        cached_data = await self.get_kv_data(cache_key, None)
        now = time.time()

        if cached_data:
            ts = cached_data.get("timestamp", 0)
            if now - ts < self.search_cache_expiry_hours * 3600:
                astrbot_logger.info(f"Using cached search result for: {keyword}")
                search_results = cached_data.get("results", [])
            else:
                search_results = None
        else:
            search_results = None

        if not search_results:
            yield event.plain_result(f"⏳ 正在 B站 搜索: {keyword}...")
            client = await HttpClient.get_client()
            search_results = []
            try:
                res = await client.get(
                    "https://api.bilibili.com/x/web-interface/search/type",
                    params={
                        "search_type": "bili_user",
                        "keyword": keyword,
                        "page": 1
                    },
                    timeout=10
                )
                if res.status_code == 200:
                    data = res.json()
                    if data["code"] == 0:
                        items = data["data"].get("result", [])
                        for item in items:
                            search_results.append({
                                "uid": str(item["mid"]),
                                "username": item["uname"],
                                "face": "https:" + item["upic"] if not item["upic"].startswith("http") else item["upic"],
                                "is_live": False, # Search result doesn't guarantee live status
                                "has_live": True,
                                "has_dynamic": True
                            })
                
                # Update Cache
                if search_results:
                    await self.put_kv_data(cache_key, {
                        "results": search_results,
                        "timestamp": now
                    })
            except Exception as e:
                astrbot_logger.error(f"Search failed: {e}")
                yield event.plain_result(f"❌ 搜索失败: {e}")
                return

        if not search_results:
            yield event.plain_result(f"🔍 未找到名为 '{keyword}' 的 UP 主")
            return

        yield event.plain_result(f"🔍 为您找到 {len(search_results)} 位相关 UP 主")

        # 2. Render Card with Adaptive Count
        bg_data = await self._get_background_uri()
        bg_uri = bg_data["uri"]
        bg_w = bg_data["width"]
        bg_h = bg_data["height"]

        # Calculate max cards based on area or row/col
        # Card size is approx 280x280 + 25px gap
        # Approximate cols = bg_w // 305
        # Approximate rows = (bg_h - header_h) // 305
        cols = max(1, bg_w // 305)
        rows = max(1, (bg_h - 150) // 305)
        max_cards = cols * rows

        astrbot_logger.info(f"Viewport size: {bg_w}x{bg_h}, calculated max cards: {max_cards}")
        
        display_results = search_results[:max_cards]
        
        # 3. Render
        template_path = Path(__file__).parent / "theme" / "templates"
        try:
            img_bytes = await render_template(
                template_path,
                "sub_list.html.jinja",
                {
                    "subs": display_results,
                    "bg_image_uri": bg_uri,
                    "page_title": f"搜索结果: {keyword}"
                },
                viewport={"width": bg_w, "height": 10},
                selector="body",
            )
            yield event.chain_result([Comp.Image.fromBytes(img_bytes)])
        except Exception as e:
            astrbot_logger.error(f"Render search results failed: {e}")
            yield event.plain_result(f"❌ 搜索结果渲染失败")

        # After search, trigger a cleanup check
        asyncio.create_task(self._cleanup_temp_files())

    @filter.command("b站订阅列表", alias={"bilibili 订阅列表", "list_bili_sub"})
    async def list_subscriptions(self, event: AstrMessageEvent):
        target_id = self._get_target_id(event)
        if not target_id:
            return

        subs = self.db.get_subscriptions(target_id)
        if not subs:
            yield event.plain_result("📭 当前群组无订阅")
            return

        # 1. Group by UID
        subs_map = {}
        for sub in subs:
            if sub.uid not in subs_map:
                subs_map[sub.uid] = {
                    "uid": sub.uid,
                    "username": sub.username,
                    "has_dynamic": False,
                    "has_live": False,
                }

            if sub.sub_type == "dynamic":
                subs_map[sub.uid]["has_dynamic"] = True
            elif sub.sub_type == "live":
                subs_map[sub.uid]["has_live"] = True

        uids = list(subs_map.keys())

        # 2. Fetch User Info (Faces) Concurrently
        client = await HttpClient.get_client()
        uid_face_map = {}
        sem = asyncio.Semaphore(5)

        async def fetch_face(uid):
            async with sem:
                try:
                    res = await client.get(
                        "https://api.bilibili.com/x/web-interface/card",
                        params={"mid": uid},
                        timeout=5,
                    )
                    if res.status_code == 200:
                        data = res.json()
                        if data["code"] == 0:
                            return uid, data["data"]["card"]["face"]
                except Exception as e:
                    astrbot_logger.warning(f"Fetch face failed for {uid}: {e}")
            return uid, "http://i0.hdslb.com/bfs/face/member/noface.jpg"

        tasks = [fetch_face(uid) for uid in uids]

        # 3. Fetch Live Status for Live Subs
        live_status_map = {}
        live_uids = [uid for uid, info in subs_map.items() if info["has_live"]]

        if live_uids:
            try:
                live_infos = await self.scheduler.live_platform.batch_get_status(
                    live_uids
                )
                for info in live_infos:
                    live_status_map[str(info.uid)] = info.live_status == 1
            except Exception as e:
                astrbot_logger.error(f"Batch get live status failed: {e}")

        if tasks:
            yield event.plain_result("⏳ 正在获取订阅详细信息...")
            results = await asyncio.gather(*tasks)
            uid_face_map = dict(results)

        # 4. Prepare Context
        all_subs = []
        for uid, info in subs_map.items():
            info["face"] = uid_face_map.get(str(uid), "")
            if info["has_live"]:
                info["is_live"] = live_status_map.get(str(uid), False)
            else:
                info["is_live"] = False
            all_subs.append(info)

        # 4. Render
        template_path = Path(__file__).parent / "theme" / "templates"
        bg_data = await self._get_background_uri()

        try:
            img_bytes = await render_template(
                template_path,
                "sub_list.html.jinja",
                {"subs": all_subs, "bg_image_uri": bg_data["uri"]},
                viewport={"width": bg_data["width"], "height": 10},
                selector="body",
            )
            yield event.chain_result([Comp.Image.fromBytes(img_bytes)])

        except Exception as e:
            astrbot_logger.error(f"Render sub list failed: {e}")
            yield event.plain_result(f"❌ 列表渲染失败: {e}")

    def get_effective_platform_name(self) -> str:
        if self.platform_name == "auto":
            available = [
                p.meta().id for p in self.context.platform_manager.platform_insts
            ]
            return available[0] if available else "llonebot"
        return self.platform_name
