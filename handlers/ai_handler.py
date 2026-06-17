from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.core.agent.tool import ToolSet

from ..workflows import format_workflow_list, run_bili_workflow, workflow_from_tool
from ..workflows.runtime import message_event_from_tool_arg


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
            return event.plain_result("❌ 当前会话没有可用的 B站 AI workflow 工具")

        try:
            provider_id = await self.star.context.get_current_chat_provider_id(
                umo=event.unified_msg_origin,
            )
            llm_resp = await self.star.context.tool_loop_agent(
                event=event,
                chat_provider_id=provider_id,
                prompt=prompt,
                tools=selected_tools,
                system_prompt=self._agent_system_prompt(),
                max_steps=self.star.ai_max_steps,
                tool_call_timeout=self.star.ai_tool_timeout_sec,
            )
            return event.plain_result(llm_resp.completion_text or "已完成")
        except Exception as exc:
            logger.error(f"Bilibili Agent 调用失败: {exc}", exc_info=True)
            return event.plain_result(f"❌ Agent 调用失败: {exc}")

    def _select_tools(self) -> ToolSet:
        preferred = ["bili_workflow"]
        fallback = [
            "bili_search_up",
            "bili_add_dynamic_sub",
            "bili_add_live_sub",
            "bili_list_subs",
            "bili_remove_sub",
        ]
        tool_mgr = self.star.context.get_llm_tool_manager()
        selected_tools = ToolSet()
        for name in preferred:
            tool = tool_mgr.get_func(name)
            if tool:
                selected_tools.add_tool(tool)
        if not selected_tools.empty():
            return selected_tools
        for name in fallback:
            tool = tool_mgr.get_func(name)
            if tool:
                selected_tools.add_tool(tool)
        return selected_tools

    async def run_workflow(
        self,
        event,
        workflow: str,
        target: str = "",
        params: object = "",
    ) -> str:
        if not self.star.enable_ai_tools:
            return "AI 工具已关闭。"
        actual_event = message_event_from_tool_arg(event)
        request = workflow_from_tool(workflow, target, params)
        result = await run_bili_workflow(self.star, actual_event, request)
        return result.text

    async def search_up(self, event, keyword: str) -> str:
        return await self.run_workflow(event, "search_up", keyword, {"keyword": keyword})

    async def add_subscription(
        self,
        event: AstrMessageEvent,
        uid: str,
        sub_type: str,
    ) -> str:
        return await self.run_workflow(
            event,
            "add_subscription",
            uid,
            {"uid": uid, "sub_type": sub_type},
        )

    async def remove_subscription(
        self,
        event: AstrMessageEvent,
        uid: str,
        sub_type: str,
    ) -> str:
        return await self.run_workflow(
            event,
            "remove_subscription",
            uid,
            {"uid": uid, "sub_type": sub_type},
        )

    async def list_subscriptions(self, event: AstrMessageEvent) -> str:
        return await self.run_workflow(event, "list_subscriptions")

    def _agent_system_prompt(self) -> str:
        return (
            "你正在使用 Bilibili 推送插件的 workflow 工具。"
            "当用户只给出 UP 主名称或模糊关键词时，先调用 search_up 或 add_subscription 生成候选任务，"
            "不要自行猜 UID。AI workflow 会在候选可信度较高时自动进入确认流程；"
            "只有用户给出明确 UID，或用户通过 pending task 确认后，才可以写入订阅。"
            "删除订阅时必须要求明确 UID 和订阅类型。"
            "\n\n"
            + format_workflow_list()
        )
