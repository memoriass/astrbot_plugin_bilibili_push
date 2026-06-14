from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.core.agent.tool import ToolSet

from ..core.http import HttpClient
from ..database.db_manager import Subscription


class AiToolHandler:
    def __init__(self, star):
        self.star = star

    async def run_agent(self, event: AstrMessageEvent, prompt: str):
        if not self.star.enable_ai_agent_entry:
            return event.plain_result("⚠️ AI Agent 入口已关闭")
        if not prompt:
            return event.plain_result(
                "❌ 请输入问题，例如：b站助手 帮我搜索影视飓风并订阅动态"
            )

        selected_tools = self._select_tools()
        if selected_tools.empty():
            return event.plain_result("❌ 当前会话没有可用的 B站 AI 工具")

        try:
            provider_id = await self.star.context.get_current_chat_provider_id(
                umo=event.unified_msg_origin,
            )
            llm_resp = await self.star.context.tool_loop_agent(
                event=event,
                chat_provider_id=provider_id,
                prompt=prompt,
                tools=selected_tools,
                max_steps=self.star.ai_max_steps,
                tool_call_timeout=self.star.ai_tool_timeout_sec,
            )
            return event.plain_result(llm_resp.completion_text or "已完成")
        except Exception as exc:
            logger.error(f"Bilibili Agent 调用失败: {exc}", exc_info=True)
            return event.plain_result(f"❌ Agent 调用失败: {exc}")

    def _select_tools(self) -> ToolSet:
        tool_names = [
            "bili_search_up",
            "bili_add_dynamic_sub",
            "bili_add_live_sub",
            "bili_list_subs",
            "bili_remove_sub",
        ]
        tool_mgr = self.star.context.get_llm_tool_manager()
        selected_tools = ToolSet()
        for name in tool_names:
            tool = tool_mgr.get_func(name)
            if tool:
                selected_tools.add_tool(tool)
        return selected_tools

    async def search_up(self, keyword: str) -> str:
        if not self.star.enable_ai_tools:
            return "AI 工具已关闭。"
        if not keyword.strip():
            return "搜索关键词不能为空。"

        client = await HttpClient.get_client()
        try:
            response = await client.get(
                "https://api.bilibili.com/x/web-interface/search/type",
                params={"search_type": "bili_user", "keyword": keyword, "page": 1},
                timeout=10,
            )
            if response.status_code != 200:
                return f"搜索失败，HTTP {response.status_code}。"
            data = response.json()
            if data.get("code") != 0:
                return f"搜索失败，code={data.get('code')}。"
            results = data.get("data", {}).get("result", [])
            if not results:
                return f"未找到关键词“{keyword}”对应的 UP 主。"
            lines = [f"搜索结果（关键词：{keyword}）:"]
            for idx, item in enumerate(results[:8], start=1):
                lines.append(
                    f"{idx}. {item.get('uname', '')} | UID={item.get('mid', '')}"
                )
            return "\n".join(lines)
        except Exception as exc:
            logger.error(f"AI 搜索 UP 失败: {exc}", exc_info=True)
            return f"搜索失败：{exc}"

    async def add_subscription(
        self,
        event: AstrMessageEvent,
        uid: str,
        sub_type: str,
    ) -> str:
        if not self.star.enable_ai_tools:
            return "AI 工具已关闭。"
        if sub_type not in {"dynamic", "live"}:
            return "sub_type 仅支持 dynamic 或 live。"

        user_info = await self.star.parser.get_user_info(uid)
        if not user_info:
            return f"无法获取 UID={uid} 的用户信息。"

        target_id = event.unified_msg_origin
        existing = self.star.db.get_subscriptions(target_id)
        if any(sub.uid == str(uid) and sub.sub_type == sub_type for sub in existing):
            return f"订阅已存在：{user_info['username']} ({uid}) [{sub_type}]"

        categories = [1, 2, 3, 4, 5, 6] if sub_type == "dynamic" else [1, 2, 3]
        sub = Subscription(
            uid=uid,
            username=user_info["username"],
            sub_type=sub_type,
            target_id=target_id,
            categories=categories,
            tags=[],
            enabled=True,
        )
        if not self.star.db.add_subscription(sub):
            return "写入订阅失败，请稍后重试。"
        return f"已添加订阅：{user_info['username']} ({uid}) [{sub_type}]"

    def remove_subscription(
        self,
        event: AstrMessageEvent,
        uid: str,
        sub_type: str,
    ) -> str:
        if not self.star.enable_ai_tools:
            return "AI 工具已关闭。"
        if sub_type not in {"dynamic", "live"}:
            return "sub_type 仅支持 dynamic 或 live。"
        target_id = event.unified_msg_origin
        ok = self.star.db.remove_subscription(uid, sub_type, target_id)
        if not ok:
            return f"未找到订阅：UID={uid}, type={sub_type}"
        return f"已删除订阅：UID={uid}, type={sub_type}"

    def list_subscriptions(self, event: AstrMessageEvent) -> str:
        if not self.star.enable_ai_tools:
            return "AI 工具已关闭。"
        target_id = event.unified_msg_origin
        subs = self.star.db.get_subscriptions(target_id)
        if not subs:
            return "当前会话暂无订阅。"

        grouped: dict[str, set[str]] = {}
        names: dict[str, str] = {}
        for sub in subs:
            grouped.setdefault(sub.uid, set()).add(sub.sub_type)
            names[sub.uid] = sub.username

        lines = ["当前会话订阅列表："]
        for uid in sorted(grouped.keys()):
            sub_types = "/".join(sorted(grouped[uid]))
            lines.append(f"- {names.get(uid, uid)} | UID={uid} | type={sub_types}")
        return "\n".join(lines)
