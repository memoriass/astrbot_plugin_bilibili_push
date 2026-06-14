from __future__ import annotations

import base64
import importlib.util
import time
from pathlib import Path


class TemplatePreviewService:
    def __init__(self, plugin):
        self.plugin = plugin
        self.preview_dir = Path(plugin.plugin_dir) / "template_previews"

    def list_previews(self) -> list[dict]:
        if not self.preview_dir.exists():
            return []
        paths = sorted(self.preview_dir.glob("*.png"), key=_preview_sort_key)
        return [self._file_info(path) for path in paths if path.is_file()]

    def preview_data(self, name: str) -> dict:
        path = self._resolve_preview_path(name)
        payload = base64.b64encode(path.read_bytes()).decode("ascii")
        return {
            **self._file_info(path),
            "data_url": f"data:image/png;base64,{payload}",
        }

    async def generate(self, seed: int | None = None) -> list[dict]:
        script = self.plugin.plugin_dir / "scripts" / "generate_template_previews.py"
        if not script.exists():
            raise FileNotFoundError("模板预览脚本不存在。")
        module = _load_preview_script(script)
        actual_seed = int(seed or time.strftime("%Y%m%d"))
        paths = await module.render_previews(self.preview_dir, actual_seed)
        sheet = self.preview_dir / "_contact_sheet.png"
        module.make_contact_sheet(paths, sheet)
        return self.list_previews()

    def _resolve_preview_path(self, name: str) -> Path:
        filename = Path(str(name or "")).name
        if not filename.endswith(".png") or filename != str(name or ""):
            raise ValueError("预览文件名不合法。")
        path = (self.preview_dir / filename).resolve(strict=False)
        path.relative_to(self.preview_dir.resolve(strict=False))
        if not path.is_file():
            raise FileNotFoundError("预览文件不存在。")
        return path

    def _file_info(self, path: Path) -> dict:
        stat = path.stat()
        return {
            "name": path.name,
            "label": _label(path.stem),
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        }


def _load_preview_script(script: Path):
    spec = importlib.util.spec_from_file_location(
        "_bilibili_template_preview_script",
        script,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载模板预览脚本。")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _preview_sort_key(path: Path) -> tuple[int, str]:
    return (0 if path.name == "_contact_sheet.png" else 1, path.name)


def _label(stem: str) -> str:
    labels = {
        "_contact_sheet": "总览拼图",
        "dynamic_movie_card": "动态推送卡片",
        "movie_card_live": "直播推送卡片",
        "parser_bili": "链接解析卡片",
        "sub_add_dynamic": "动态订阅结果",
        "sub_add_live": "直播订阅结果",
        "sub_list_login_accounts": "登录账号状态",
        "sub_list_subscriptions": "订阅列表",
    }
    return labels.get(stem, stem)
