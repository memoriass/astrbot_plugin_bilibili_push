"""HTTP 客户端封装"""

from typing import TYPE_CHECKING, Optional

import httpx

if TYPE_CHECKING:
    from astrbot.api.star import Star


class HttpClient:
    _client: httpx.AsyncClient | None = None
    _buvid_initialized: bool = False
    _star_instance: Optional["Star"] = None

    # Account Pool
    # Structure: [{"uid": str, "name": str, "face": str, "cookies": dict, "valid": bool}]
    _accounts: list[dict] = []
    _current_account_index: int = 0

    @classmethod
    async def set_star_instance(cls, star: "Star"):
        cls._star_instance = star
        await cls.load_accounts()

    @classmethod
    async def load_accounts(cls):
        if cls._star_instance:
            cls._accounts = await cls._star_instance.get_kv_data(
                "bilibili_push_accounts", []
            )
            # Migrate old single cookie if exists and pool is empty
            if not cls._accounts:
                old_cookies = await cls._star_instance.get_kv_data("bili_cookies", {})
                if not old_cookies:
                    # Try another common key from previous versions if any
                    old_cookies = await cls._star_instance.get_kv_data("bilibili_cookies", {})
                
                if old_cookies:
                    # Generic migration entry
                    cls._accounts.append(
                        {
                            "uid": "default",
                            "name": "Default Account",
                            "face": "",
                            "cookies": old_cookies,
                            "valid": True,
                        }
                    )
                    await cls.save_accounts()

            # Reset index
            cls._current_account_index = 0

    @classmethod
    async def save_accounts(cls):
        if cls._star_instance:
            await cls._star_instance.put_kv_data("bilibili_push_accounts", cls._accounts)

    @classmethod
    async def add_account(cls, uid: str, name: str, face: str, cookies: dict):
        # Update if exists
        for acc in cls._accounts:
            if str(acc.get("uid")) == str(uid):
                acc["name"] = name
                acc["face"] = face
                acc["cookies"] = cookies
                acc["valid"] = True
                await cls.save_accounts()
                # Update current client if it matches
                if cls._client:
                    cls._client.cookies.update(cookies)
                return

        # Add new
        cls._accounts.append(
            {
                "uid": str(uid),
                "name": name,
                "face": face,
                "cookies": cookies,
                "valid": True,
            }
        )
        await cls.save_accounts()

    @classmethod
    async def get_accounts(cls) -> list[dict]:
        if not cls._accounts and cls._star_instance:
            await cls.load_accounts()
        return cls._accounts

    @classmethod
    async def rotate_account(cls) -> bool:
        """Switch to next valid account. Returns True if successful, False if no valid accounts."""
        start_index = cls._current_account_index
        attempts = 0
        total = len(cls._accounts)
        if total == 0:
            return False

        while attempts < total:
            cls._current_account_index = (cls._current_account_index + 1) % total
            acc = cls._accounts[cls._current_account_index]
            if acc.get("valid", True):
                if cls._client:
                    cls._client.cookies.clear()
                    cls._client.cookies.update(acc["cookies"])
                from ..utils.logger import logger

                logger.info(
                    f"Switched to Bilibili account: {acc.get('name')} (UID: {acc.get('uid')})"
                )
                return True
            attempts += 1

        return False

    @classmethod
    async def set_current_account_status(cls, valid: bool = True, status_code: int = None):
        if not cls._accounts: return
        acc = cls._accounts[cls._current_account_index]
        acc["valid"] = valid
        acc["status_code"] = status_code
        await cls.save_accounts()

    @classmethod
    async def invalidate_current_account(cls, status_code: int = None):
        if not cls._accounts:
            return
        acc = cls._accounts[cls._current_account_index]
        acc["valid"] = False
        acc["status_code"] = status_code
        from ..utils.logger import logger

        logger.warning(
            f"Marking account invalid (Code {status_code}): {acc.get('name')} (UID: {acc.get('uid')})"
        )
        await cls.save_accounts()
        await cls.rotate_account()

    @classmethod
    async def get_client(cls) -> httpx.AsyncClient:
        if cls._client is None or cls._client.is_closed:
            cls._client = httpx.AsyncClient(
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://www.bilibili.com/",
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
                timeout=20.0,
                follow_redirects=True,
                cookies={},
                verify=False,
            )
            cls._buvid_initialized = False

            # Load accounts if not loaded
            if not cls._accounts:
                await cls.load_accounts()

            # Apply current account cookies
            if cls._accounts:
                acc = cls._accounts[cls._current_account_index]
                if not acc.get("valid", True):
                    # Try to find a valid one
                    await cls.rotate_account()
                    acc = cls._accounts[cls._current_account_index]

                if acc.get("valid", True):
                    cls._client.cookies.update(acc["cookies"])
                    cls._buvid_initialized = True

        if not cls._buvid_initialized:
            try:
                await cls._client.get("https://www.bilibili.com/", timeout=5.0)
                await cls._client.get(
                    "https://api.bilibili.com/x/frontend/finger/spi", timeout=5.0
                )
                cls._buvid_initialized = True
            except Exception as e:
                from ..utils.logger import logger

                logger.warning(f"初始化 B站 Cookies 失败: {e}")

        return cls._client

    @classmethod
    async def close(cls):
        if cls._client:
            await cls._client.aclose()
            cls._client = None
