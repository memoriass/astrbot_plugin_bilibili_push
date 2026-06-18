import random
import base64
import mimetypes
from pathlib import Path


def get_random_background(folder_path: Path) -> dict:
    """随机读取背景图并转为 data URI。"""
    if not folder_path.exists():
        try:
            folder_path.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return {"uri": "", "width": 800, "height": 600}

    bg_files = [
        f
        for f in folder_path.iterdir()
        if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
    ]

    if not bg_files:
        return {"uri": "", "width": 800, "height": 600}

    bg_file = random.choice(bg_files)
    try:
        mime_type, _ = mimetypes.guess_type(bg_file)
        with open(bg_file, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
            return {
                "uri": f"data:{mime_type or 'image/jpeg'};base64,{b64_data}",
                "width": 800,
                "height": 600,
            }
    except Exception:
        return {"uri": "", "width": 800, "height": 600}


def get_assets_path() -> Path:
    """获取资源文件根目录"""
    return Path(__file__).parent / "resources"


def get_template_path() -> Path:
    """获取模板目录。"""
    return get_assets_path() / "templates"
