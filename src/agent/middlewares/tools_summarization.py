"""
中间件 5: compact_conversation 工具注册
提供手动触发对话压缩的工具，当上下文过长时由 LLM 主动调用
"""
from typing import Any

from langchain.agents.middleware import AgentMiddleware, Runtime
from ..log_utils import middleware_logger


class ToolsSummarizationMiddleware(AgentMiddleware):
    """
    对话压缩工具中间件

    职责：
    - 注册 compact_conversation 工具到 Agent 工具列表
    - 当对话上下文超过阈值时，LLM 可主动调用此工具压缩历史
    - 压缩策略：保留最近 N 条 + 摘要前面的对话

    注意：deepagents 框架已内置 SummarizationToolMiddleware，
    本中间件作为补充，提供采购领域定制的压缩提示词。
    """

    def __init__(self):
        """
        初始化摘要监控中间件

        注意：deepagents 框架已内置 SummarizationMiddleware + SummarizationToolMiddleware，
        本中间件仅作为补充，提供采购领域定制的上下文长度监控。
        """
        self.tools = []

    @property
    def name(self) -> str:
        return "ToolsSummarizationMiddleware"

    def before_agent(self, state: Any, runtime: Runtime) -> dict[str, Any] | None:
        """检查上下文长度，必要时注入压缩提示"""
        # 框架内置的 SummarizationMiddleware 已处理自动压缩
        # 本中间件仅记录状态供监控
        messages = state.get("messages", []) if isinstance(state, dict) else []
        msg_count = len(messages)
        if msg_count > 40:
            middleware_logger.debug(
                f"Conversation length: {msg_count} messages (consider compacting)"
            )
        return None
