from __future__ import annotations

from .manager_crud import AccountCrud, SubscriptionCrud
from .manager_overview import ManagerOverviewService
from .manager_response import error, ok, request_args, request_json
from .template_preview import TemplatePreviewService


PLUGIN_NAME = "astrbot_plugin_bilibili_push"


def register_bilibili_web_apis(context, plugin):
    api = BilibiliManagerApi(plugin)
    routes = [
        ("overview", api.overview, ["GET"], "Bilibili manager overview"),
        ("subscriptions/create", api.create_subscription, ["POST"], "Create subscription"),
        ("subscriptions/update", api.update_subscription, ["POST"], "Update subscription"),
        ("subscriptions/delete", api.delete_subscription, ["POST"], "Delete subscription"),
        ("subscriptions/enabled", api.set_subscription_enabled, ["POST"], "Toggle subscription"),
        ("pending/clear", api.clear_pending, ["POST"], "Clear pending tasks"),
        ("checks/live", api.manual_live_check, ["POST"], "Run manual live check"),
        ("accounts/upsert", api.upsert_account, ["POST"], "Create or update account"),
        ("accounts/delete", api.delete_account, ["POST"], "Delete account"),
        ("accounts/valid", api.set_account_valid, ["POST"], "Set account validity"),
        ("templates/list", api.list_templates, ["GET"], "List template previews"),
        ("templates/preview", api.preview_template, ["GET"], "Read template preview"),
        ("templates/generate", api.generate_templates, ["POST"], "Generate template previews"),
    ]
    for endpoint, handler, methods, description in routes:
        context.register_web_api(
            f"/{PLUGIN_NAME}/{endpoint}",
            handler,
            methods,
            description,
        )
    return api


class BilibiliManagerApi:
    def __init__(self, plugin):
        self.plugin = plugin
        self.overview_service = ManagerOverviewService(plugin)
        self.subscriptions = SubscriptionCrud(plugin)
        self.accounts = AccountCrud()
        self.templates = TemplatePreviewService(plugin)

    async def overview(self):
        return ok(await self.overview_service.build())

    async def create_subscription(self):
        return await self.subscriptions.create(await request_json())

    async def update_subscription(self):
        return await self.subscriptions.update(await request_json())

    async def delete_subscription(self):
        return self.subscriptions.delete(await request_json())

    async def set_subscription_enabled(self):
        return self.subscriptions.set_enabled(await request_json())

    async def clear_pending(self):
        count = await self.plugin.pending_store.clear()
        return ok({"cleared": count})

    async def manual_live_check(self):
        payload = await request_json()
        target_id = str(payload.get("target_id") or "").strip()
        if not target_id:
            return error("target_id 参数不能为空。")
        pushed = await self.plugin.scheduler.manual_live_check(target_id)
        return ok({"target_id": target_id, "pushed": pushed})

    async def upsert_account(self):
        return await self.accounts.upsert(await request_json())

    async def delete_account(self):
        return await self.accounts.delete(await request_json())

    async def set_account_valid(self):
        return await self.accounts.set_valid(await request_json())

    async def list_templates(self):
        return ok({"previews": self.templates.list_previews()})

    async def preview_template(self):
        name = str(request_args().get("name") or "").strip()
        if not name:
            return error("name 参数不能为空。")
        try:
            return ok({"preview": self.templates.preview_data(name)})
        except (FileNotFoundError, ValueError) as exc:
            return error(str(exc))

    async def generate_templates(self):
        payload = await request_json()
        seed = payload.get("seed")
        try:
            seed = int(seed) if seed not in (None, "") else None
            previews = await self.templates.generate(seed)
        except Exception as exc:
            return error(f"模板预览生成失败：{exc}")
        return ok({"previews": previews})
