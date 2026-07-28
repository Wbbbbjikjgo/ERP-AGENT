"""
中间件 7: 沙箱熔断器
连续 N 次沙箱工具调用失败 → 短路 → 降级响应（避免无限重试拖垮系统）
"""
import time
from typing import Any, Callable, Awaitable

from langchain_core.messages import ToolMessage
from langgraph.types import Command
from langchain.agents.middleware import AgentMiddleware, Runtime, ToolCallRequest
from ..log_utils import middleware_logger


class SandboxCircuitBreakerMiddleware(AgentMiddleware):
    """
    沙箱熔断器中间件

    三态模型：
    - CLOSED（正常）：所有工具调用正常通过
    - OPEN（熔断）：沙箱相关工具直接返回降级响应，不调用 handler
    - HALF_OPEN（探测）：熔断后经过 recovery_timeout，允许一次试探

    触发条件：连续 failure_threshold 次沙箱工具调用失败
    恢复条件：HALF_OPEN 状态下一次成功调用 → 回到 CLOSED

    仅拦截沙箱相关工具（execute, run_code 等），MCP/ERP 工具不受影响。
    """

    # 沙箱相关工具名（这些工具依赖沙箱容器）
    SANDBOX_TOOLS = {"execute", "run_code", "run_python", "shell", "bash"}

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
    ):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failure_count: int = 0
        self._state: str = "CLOSED"  # CLOSED / OPEN / HALF_OPEN
        self._last_failure_time: float = 0
        self.tools = []

    @property
    def name(self) -> str:
        return "SandboxCircuitBreakerMiddleware"

    def _is_sandbox_tool(self, tool_name: str) -> bool:
        """判断工具是否依赖沙箱"""
        return tool_name.lower() in self.SANDBOX_TOOLS

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        """拦截沙箱工具调用，实现熔断逻辑"""
        tool_name = request.tool_call.get("name", "")

        # 非沙箱工具直接通过
        if not self._is_sandbox_tool(tool_name):
            return await handler(request)

        # 熔断器状态判断
        if self._state == "OPEN":
            # 检查是否到达恢复时间
            if time.time() - self._last_failure_time >= self._recovery_timeout:
                self._state = "HALF_OPEN"
                middleware_logger.info("Circuit breaker → HALF_OPEN (attempting recovery)")
            else:
                # 直接返回降级响应
                middleware_logger.warning(
                    f"Circuit breaker OPEN: skipping sandbox tool '{tool_name}'"
                )
                return ToolMessage(
                    content=f"[沙箱暂时不可用] 工具 '{tool_name}' 被熔断器拦截。"
                            f"沙箱服务正在恢复中，请稍后重试或使用其他工具完成任务。",
                    tool_call_id=request.tool_call.get("id", ""),
                    status="error",
                )

        # CLOSED 或 HALF_OPEN：执行工具
        try:
            result = await handler(request)
            # 成功 → 重置
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(tool_name, e)
            # 返回错误消息而非抛出异常（让 Agent 知道失败了但可以继续）
            return ToolMessage(
                content=f"[沙箱调用失败] {tool_name}: {str(e)[:200]}。"
                        f"连续失败 {self._failure_count} 次。",
                tool_call_id=request.tool_call.get("id", ""),
                status="error",
            )

    def _on_success(self):
        """工具调用成功"""
        if self._state == "HALF_OPEN":
            middleware_logger.info("Circuit breaker → CLOSED (sandbox recovered)")
        self._failure_count = 0
        self._state = "CLOSED"

    def _on_failure(self, tool_name: str, error: Exception):
        """工具调用失败"""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self._failure_threshold:
            self._state = "OPEN"
            middleware_logger.error(
                f"Circuit breaker → OPEN after {self._failure_count} failures. "
                f"Last error: {tool_name}: {error}"
            )
        else:
            middleware_logger.warning(
                f"Sandbox tool failure ({self._failure_count}/{self._failure_threshold}): "
                f"{tool_name}: {error}"
            )
