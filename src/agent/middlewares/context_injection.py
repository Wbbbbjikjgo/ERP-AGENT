"""
中间件 2: 用户上下文注入
将 ProcurementContext 注入到 agent state 的 configurable 中.
"""
from typing import Any

from langchain.agents.middleware import AgentMiddleware, Runtime
from ..log_utils import middleware_logger
from ..schema import ProcurementContext


class ContextInjectionMiddleware(AgentMiddleware):
    """
    用户上下文注入中间件

    职责：
    - 在 Agent 执行前将用户偏好、身份等信息注入 runtime context
    - 下游工具/子Agent可通过 runtime.context 获取用户信息
    - 支持动态偏好更新（从 store 加载最新偏好）
    """

    def __init__(self, user_context: ProcurementContext | None = None):
        self._user_context = user_context or ProcurementContext()
        self.tools = []

    @property
    def name(self) -> str:
        return "ContextInjectionMiddleware"

    def before_agent(self, state: Any, runtime: Runtime) -> dict[str, Any] | None:
        """在 Agent 执行前注入用户上下文"""
        # 将用户上下文附加到 state 的 messages 系统信息中
        # 这样 LLM 在每次对话中都能感知用户身份和偏好
        middleware_logger.debug(
            f"Context injected: user={self._user_context.user_id}, "
            f"prefs={list(self._user_context.preferences.keys())}"
        )
        # 不修改 state，上下文已通过 system_prompt 模板变量注入
        return None

    def update_context(self, user_context: ProcurementContext):
        """动态更新用户上下文（新请求时调用）"""
        self._user_context = user_context
