"""
中间件 6: 用户偏好自动提取 + 持久化
对话结束后从消息中提取用户偏好 → store.aput() 更新。
"""
import json
from typing import Any

from langchain.agents.middleware import AgentMiddleware, Runtime
from ..log_utils import middleware_logger


class MemoryUpdateMiddleware(AgentMiddleware):
    """
    用户偏好自动更新中间件

    职责：
    - after_agent: 从最近对话中提取用户偏好信号
    - 提取维度：preferred_chart_type, recent_suppliers, preferred_output
    - 通过 store.aput() 持久化到 MongoDB（跨会话保留）

    提取规则（基于关键词匹配，无需额外 LLM 调用）：
    - "以后都用饼图" → preferred_chart_type = "pie"
    - "用表格展示" → preferred_output = "table"
    - 查询了某供应商 → recent_suppliers 追加
    """

    # 图表偏好关键词映射
    CHART_KEYWORDS = {
        "饼图": "pie", "柱状图": "bar", "折线图": "line",
        "散点图": "scatter", "雷达图": "radar", "环形图": "donut",
        "热力图": "heatmap", "面积图": "area",
    }

    OUTPUT_KEYWORDS = {
        "表格": "table", "json": "json", "markdown": "markdown",
        "列表": "list", "图表": "chart",
    }

    def __init__(self, store=None, user_id: str = "default_user"):
        self._store = store
        self._user_id = user_id
        self.tools = []

    @property
    def name(self) -> str:
        return "MemoryUpdateMiddleware"

    def after_agent(self, state: Any, runtime: Runtime) -> dict[str, Any] | None:
        """Agent 执行后提取并持久化用户偏好"""
        if self._store is None:
            return None

        messages = state.get("messages", []) if isinstance(state, dict) else []
        if not messages:
            return None

        # 仅分析最近的用户消息（最后 3 条 user message）
        user_messages = [
            m for m in messages[-10:]
            if hasattr(m, "type") and m.type == "human"
        ][-3:]

        if not user_messages:
            return None

        preferences_updates = {}
        for msg in user_messages:
            content = msg.content if hasattr(msg, "content") else str(msg)
            if not isinstance(content, str):
                continue

            # 提取图表偏好
            for keyword, chart_type in self.CHART_KEYWORDS.items():
                if keyword in content and ("以后" in content or "默认" in content or "总是" in content):
                    preferences_updates["preferred_chart_type"] = chart_type

            # 提取输出格式偏好
            for keyword, output_fmt in self.OUTPUT_KEYWORDS.items():
                if keyword in content and ("用" in content or "格式" in content):
                    preferences_updates["preferred_output"] = output_fmt

        # 持久化更新
        if preferences_updates:
            try:
                namespace = ("user-preferences", self._user_id)
                self._store.put(
                    namespace,
                    key="preferences",
                    value=preferences_updates,
                )
                middleware_logger.info(
                    f"User preferences updated: {preferences_updates}"
                )
            except Exception as e:
                middleware_logger.warning(f"Failed to persist preferences: {e}")

        return None
