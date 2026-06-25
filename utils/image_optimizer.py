from __future__ import annotations

import asyncio
import base64
import io
import urllib.request
from dataclasses import dataclass
from typing import Any

from PIL import Image

from .logger import logger


_IMAGE_FETCH_TIMEOUT_SEC = 8
_DEFAULT_MAX_SOURCE_BYTES = 16 * 1024 * 1024
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
)
TRANSPARENT_IMAGE_DATA_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)
_USE_ORIGINAL = object()


@dataclass(frozen=True, slots=True)
class ImageOptimizePolicy:
    max_width: int
    max_height: int
    max_pixels: int
    quality: int = 86
    max_source_bytes: int = _DEFAULT_MAX_SOURCE_BYTES


LIVE_COVER_POLICY = ImageOptimizePolicy(
    max_width=2560,
    max_height=1440,
    max_pixels=2560 * 1440,
    quality=90,
)
DYNAMIC_HERO_POLICY = ImageOptimizePolicy(
    max_width=2560,
    max_height=1600,
    max_pixels=2560 * 1600,
    quality=90,
)
AVATAR_POLICY = ImageOptimizePolicy(
    max_width=512,
    max_height=512,
    max_pixels=512 * 512,
    quality=88,
    max_source_bytes=3 * 1024 * 1024,
)


class ImageTooLarge(ValueError):
    pass


async def optimize_template_image(
    image: Any,
    policy: ImageOptimizePolicy,
    *,
    label: str = "image",
    fallback: Any = _USE_ORIGINAL,
) -> Any:
    if not image:
        return image
    try:
        return await asyncio.to_thread(_optimize_template_image_sync, image, policy)
    except ImageTooLarge as exc:
        if fallback is _USE_ORIGINAL:
            logger.warning(f"{label} 超出内置渲染上限，跳过该图片: {exc}")
            return ""
        logger.warning(f"{label} 超出内置渲染上限，使用降级图片: {exc}")
        return fallback
    except Exception as exc:
        if fallback is _USE_ORIGINAL:
            logger.warning(f"{label} 压缩失败，使用原图: {exc}")
            return image
        logger.warning(f"{label} 压缩失败，使用降级图片: {exc}")
        return fallback


def _optimize_template_image_sync(image: Any, policy: ImageOptimizePolicy) -> str:
    raw = _load_image_bytes(image, policy)
    with Image.open(io.BytesIO(raw)) as source:
        source.load()
        resized = _resize_image(source, policy)
        return _encode_image_data_uri(resized, policy)


def _load_image_bytes(image: Any, policy: ImageOptimizePolicy) -> bytes:
    if isinstance(image, bytes):
        return image
    if not isinstance(image, str):
        raise TypeError(f"unsupported image type: {type(image)!r}")
    if image.startswith("data:image/"):
        header, _, payload = image.partition(",")
        if ";base64" not in header or not payload:
            raise ValueError("unsupported image data URI")
        return base64.b64decode(payload)
    if image.startswith(("http://", "https://")):
        request = urllib.request.Request(
            image,
            headers={
                "User-Agent": _USER_AGENT,
                "Referer": "https://www.bilibili.com/",
            },
        )
        with urllib.request.urlopen(request, timeout=_IMAGE_FETCH_TIMEOUT_SEC) as response:
            size = response.headers.get("Content-Length")
            if size and int(size) > policy.max_source_bytes:
                raise ImageTooLarge(f"source too large: {size} bytes")
            data = response.read(policy.max_source_bytes + 1)
        if len(data) > policy.max_source_bytes:
            raise ImageTooLarge(f"source too large: {len(data)} bytes")
        return data
    raise ValueError("only http(s), bytes, and image data URI are supported")


def _resize_image(source: Image.Image, policy: ImageOptimizePolicy) -> Image.Image:
    image = source.convert("RGB")
    width, height = image.size
    scale = min(
        1.0,
        policy.max_width / max(width, 1),
        policy.max_height / max(height, 1),
        (policy.max_pixels / max(width * height, 1)) ** 0.5,
    )
    if scale >= 1.0:
        return image
    target_size = (
        max(1, int(width * scale)),
        max(1, int(height * scale)),
    )
    return image.resize(target_size, Image.Resampling.LANCZOS)


def _encode_image_data_uri(image: Image.Image, policy: ImageOptimizePolicy) -> str:
    out = io.BytesIO()
    try:
        image.save(out, format="WEBP", quality=policy.quality, method=4)
        mime = "image/webp"
    except Exception:
        out = io.BytesIO()
        image.save(out, format="JPEG", quality=policy.quality, optimize=True)
        mime = "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(out.getvalue()).decode('ascii')}"
