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
from .core.types import MsgImage, MsgText
from .scheduler import BilibiliScheduler
from .sub_manager import DBManager, Subscription


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

    async def initialize(self):
        await HttpClient.set_star_instance(self)
        await self.scheduler.start()

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

    @filter.command("添加b站订阅", alias={"bilibili 添加订阅", "add_bili_sub"})
    async def add_subscription(self, event: AstrMessageEvent, uid: str):
        target_id = self._get_target_id(event)
        if not target_id:
            yield event.plain_result("❌ 无法获取会话 ID")
            return

        try:
            platform = self.scheduler.bili_platform
            username = await platform.get_target_name(uid)

            if not username:
                yield event.plain_result(
                    f"❌ 无法获取 UP 主信息: {uid}。可能是 API 限制，请稍后再试。"
                )
                return

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
                yield event.plain_result(f"✅ 已添加动态订阅: {username} ({uid})")
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
            platform = self.scheduler.live_platform
            username = await platform.get_target_name(uid)
            if not username:
                yield event.plain_result(
                    f"❌ 无法获取直播间信息: {uid}。可能是 API 限制，请稍后再试。"
                )
                return

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
                yield event.plain_result(f"✅ 已添加直播订阅: {username} ({uid})")
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

        if self.db.remove_subscription(uid, "dynamic", target_id):
            yield event.plain_result(f"✅ 已取消动态订阅: {uid}")
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

        if self.db.remove_subscription(uid, "live", target_id):
            yield event.plain_result(f"✅ 已取消直播订阅: {uid}")
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

                    # Persist via new Account Pool logic
                    await HttpClient.add_account(
                        uid=str(check_data.get("mid")),
                        name=str(check_data.get("uname", "未知用户")),
                        face=str(
                            check_data.get("face", "")
                        ),  # Face is often empty in poll response, might default locally
                        cookies=new_cookies,
                    )

                    yield event.plain_result(
                        f"✅ 登录成功！已添加账号：{check_data.get('uname', '用户')} (UID: {check_data.get('mid')})"
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

        # Reuse Background Logic
        import base64
        import mimetypes
        import random

        bg_dir = self.data_dir / "backgrounds"
        bg_dir.mkdir(parents=True, exist_ok=True)

        bg_files = [
            f
            for f in bg_dir.iterdir()
            if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
        ]

        bg_image_uri = ""
        if bg_files:
            bg_file = random.choice(bg_files)
            try:
                # Compression Logic
                try:
                    import io

                    from PIL import Image

                    with Image.open(bg_file) as img:
                        # Resize if too large (e.g. width > 1200)
                        if img.width > 1200:
                            ratio = 1200 / img.width
                            new_height = int(img.height * ratio)
                            img = img.resize(
                                (1200, new_height), Image.Resampling.LANCZOS
                            )

                        # Convert to RGB (in case of PNG with transparency) for JPEG saving
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")

                        buffer = io.BytesIO()
                        img.save(
                            buffer, format="JPEG", quality=60
                        )  # Compress heavily since it's blurred
                        base64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
                        bg_image_uri = f"data:image/jpeg;base64,{base64_str}"
                        astrbot_logger.info(
                            f"Using compressed background: {bg_file.name}"
                        )
                except ImportError:
                    # Fallback if Pillow not installed
                    astrbot_logger.warning(
                        "Pillow not installed, using original image."
                    )
                    mime_type, _ = mimetypes.guess_type(bg_file)
                    if not mime_type:
                        mime_type = "image/jpeg"
                    with open(bg_file, "rb") as f:
                        bg_image_uri = f"data:{mime_type};base64,{base64.b64encode(f.read()).decode('utf-8')}"
                except Exception as e:
                    astrbot_logger.error(
                        f"Image compression failed: {e}, using original."
                    )
                    mime_type, _ = mimetypes.guess_type(bg_file)
                    if not mime_type:
                        mime_type = "image/jpeg"
                    with open(bg_file, "rb") as f:
                        bg_image_uri = f"data:{mime_type};base64,{base64.b64encode(f.read()).decode('utf-8')}"

            except Exception:
                pass

        # Render
        # Render using sub_list template
        from .theme.renderer import render_template
        template_path = Path(__file__).parent / "theme" / "templates"
        
        # Override title for login status
        # Note: The sub_list template might hardcode "SUBSCRIPTION LIST". 
        # Since we can't easily change the template title dynamically without modifying the template 
        # (unless we pass a title variable), we use it as is or pass a custom variable if supported.
        # For now, we just pass the single user as subs.
        
        img_bytes = await render_template(
            template_path,
            "sub_list.html.jinja",
            {
                "subs": display_list, 
                "bg_image_uri": bg_image_uri,
                "page_title": "登录状态" # We might need to handle this in template
            },
            viewport={"width": 1400, "height": 1000}, # Keep same viewport
            selector="body",
        )
        yield event.chain_result([MsgImage(data=img_bytes)])

        
    @filter.command("测试直播推送")
    async def test_live_push(self, event: AstrMessageEvent, uid: str = None):
        """测试直播推送: /测试直播推送 [uid]"""
        target_id = self._get_target_id(event)
        if not target_id: return

        if not uid:
            # 如果没提供 UID，检查当前群的所有订阅
            count = await self.scheduler.manual_live_check(target_id)
            yield event.plain_result(f"已触发 {count} 个直播推送测试")
        else:
            # 针对特定 UID 测试
            # 这里我们需要临时构造一个订阅关系来触发推送，或者直接利用 manual_live_check 的逻辑
            # 但 manual_live_check 是基于订阅的。
            # 简单起见，我们只能测试已订阅的 UID
            subs = self.db.get_subscriptions(target_id)
            if not any(s.uid == uid for s in subs):
                yield event.plain_result(f"⚠️ 必须先订阅 {uid} 才能测试")
                return
            
            # 手动触发逻辑
            try:
                platform = self.scheduler.live_platform
                new_status = await platform.get_status(uid)
                # 强制认为正在直播
                if new_status.live_status != 1:
                     yield event.plain_result(f"⚠️用户 {uid} ({new_status.title}) 未开播，尝试模拟开播推送...")
                     new_status.live_status = 1 # Mock
                     
                raw_post = platform._gen_current_status(new_status, 1)
                parsed_post = await platform.parse(raw_post)
                
                # Render directly
                # Find the theme
                if self.scheduler.image_template == "movie_card":
                    theme = self.scheduler.themes["movie_card"]
                else:
                    theme = self.scheduler.themes["dynamic_card"]
                    
                msgs = await theme.render(parsed_post)
                if self.on_new_post:
                    await self.on_new_post(self.platform_name, target_id, msgs)
                yield event.plain_result(f"✅ 直播测试推送已发送")
                
            except Exception as e:
                import traceback
                astrbot_logger.error(traceback.format_exc())
                yield event.plain_result(f"❌ 测试失败: {e}")

    async def _test_dynamic_render(self, event: AstrMessageEvent, uid: str, type_filter: str):
        target_id = self._get_target_id(event)
        platform = self.scheduler.bili_platform
        yield event.plain_result(f"⏳ 正在获取 {uid} 的 {type_filter} 动态...")
        
        try:
            raw_posts = await platform.get_sub_list(uid)
            if not raw_posts:
                 yield event.plain_result(f"❌ 未获取到动态 (可能是风控或无数据)")
                 return
                 
            found_post = None
            for raw_post in raw_posts:
                # 简单判断类型
                # type_filter: "video" or "image"
                is_video = raw_post.type == "DYNAMIC_TYPE_AV"
                if type_filter == "video" and is_video:
                    found_post = await platform.parse(raw_post)
                    break
                elif type_filter == "image" and not is_video:
                    found_post = await platform.parse(raw_post)
                    break
            
            if not found_post and raw_posts:
                # Fallback to first if not found specific type
                yield event.plain_result(f"⚠️ 未找到指定类型动态，使用最新一条测试")
                found_post = await platform.parse(raw_posts[0])
                
            if found_post:
                if self.scheduler.image_template == "movie_card":
                    theme = self.scheduler.themes["movie_card"]
                else:
                    theme = self.scheduler.themes["dynamic_card"]
                msgs = await theme.render(found_post)
                if self.on_new_post:
                    await self.on_new_post(self.platform_name, target_id, msgs)
                yield event.plain_result(f"✅ 动态测试推送已发送")
            else:
                yield event.plain_result(f"❌ 未找到有效动态")
                
        except Exception as e:
            import traceback
            astrbot_logger.error(traceback.format_exc())
            yield event.plain_result(f"❌ 测试失败: {e}")

    @filter.command("测试图文动态")
    async def test_dynamic_draw(self, event: AstrMessageEvent, uid: str):
        """测试图文动态: /测试图文动态 [uid]"""
        async for res in self._test_dynamic_render(event, uid, "image"):
            yield res

    @filter.command("测试视频动态")
    async def test_dynamic_video(self, event: AstrMessageEvent, uid: str):
        """测试视频动态: /测试视频动态 [uid]"""
        async for res in self._test_dynamic_render(event, uid, "video"):
            yield res

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
        from .theme.renderer import render_template

        template_path = Path(__file__).parent / "theme" / "templates"

        # 5. Background Image Logic
        import base64
        import mimetypes
        import random

        bg_dir = self.data_dir / "backgrounds"
        bg_dir.mkdir(parents=True, exist_ok=True)

        bg_files = [
            f
            for f in bg_dir.iterdir()
            if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
        ]

        bg_image_uri = ""
        if bg_files:
            bg_file = random.choice(bg_files)
            try:
                mime_type, _ = mimetypes.guess_type(bg_file)
                if not mime_type:
                    mime_type = "image/jpeg"

                with open(bg_file, "rb") as f:
                    data = f.read()
                    base64_str = base64.b64encode(data).decode("utf-8")
                    bg_image_uri = f"data:{mime_type};base64,{base64_str}"
                astrbot_logger.info(f"Using background image: {bg_file.name}")
            except Exception as e:
                astrbot_logger.error(f"Failed to load background image {bg_file}: {e}")
        else:
            astrbot_logger.info(f"No background images found in {bg_dir}")

        try:
            img_bytes = await render_template(
                template_path,
                "sub_list.html.jinja",
                {"subs": all_subs, "bg_image_uri": bg_image_uri},
                viewport={"width": 1400, "height": 1000},
                selector="body",
            )

            # Fix: Save bytes to temp file because fromFileSystem needs a path
            temp_dir = self.data_dir / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_file = temp_dir / f"sub_list_{int(time.time())}.jpg"

            with open(temp_file, "wb") as f:
                f.write(img_bytes)

            yield event.chain_result(
                [Comp.Image.fromFileSystem(str(temp_file.absolute()))]
            )

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
