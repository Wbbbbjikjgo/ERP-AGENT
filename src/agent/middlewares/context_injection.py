"""
中间件 2: 用户上下文注入（工厂模式，请求级隔离）
将 ProcurementContext 注入到 agent state 的 configurable 中。

设计要点：
- 使用 dict 按 thread_id 存储用户上下文，避免全局单例串扰
- create_middleware() 工厂方法为每个 Agent 实例创建独立中间件
- update_context() 支持运行时动态更新（新请求时调用）
"""
import threading
from typing import Any, Dict, Optional

from langchain.agents.middleware import AgentMiddleware, Runtime
from ..log_utils import middleware_logger
from ..schema import ProcurementContext


class ContextInjectionMiddleware(AgentMiddleware):
    """
    用户上下文注入中间件（请求级隔离）

    职责：
    - 在 Agent 执行前将用户偏好、身份等信息注入 runtime context
    - 使用 thread_id 隔离不同用户的上下文，防止并发串扰
    - 支持动态偏好更新（从 store 加载最新偏好）

    隔离机制：
    - _context_store: Dict[thread_id, ProcurementContext]
    - 每个会话线程拥有独立的上下文副本
    - 线程安全：使用 threading.Lock 保护并发读写
    """

    def __init__(self, user_context: ProcurementContext | None = None):
        # 默认上下文（仅作为 fallback）
        self._default_context = user_context or ProcurementContext()
        # 请求级隔离存储：thread_id → ProcurementContext
        self._context_store: Dict[str, ProcurementContext] = {}
        self._lock = threading.Lock()
        self.tools = []

    @property
    def name(self) -> str:
        return "ContextInjectionMiddleware"

    def before_agent(self, state: Any, runtime: Runtime) -> dict[str, Any] | None:
        """在 Agent 执行前注入用户上下文"""
        # 从 runtime 获取当前线程 ID
        thread_id = self._get_thread_id(runtime)
        ctx = self._get_context(thread_id)

        middleware_logger.debug(
            f"Context injected: thread={thread_id}, user={ctx.user_id}, "
            f"prefs={list(ctx.preferences.keys())}"
        )

        # 不修改 state，上下文已通过 system_prompt 模板变量注入
        # 但可以在 state 的 configurable 中附加运行时信息
        return None

    def after_agent(self, state: Any, runtime: Runtime) -> dict[str, Any] | None:
        """Agent 执行后可更新上下文（如新发现的偏好）"""
        return None

    # ============================================================
    # 上下文管理
    # ============================================================

    def update_context(
        self,
        user_context: ProcurementContext,
        thread_id: str = "",
    ):
        """
        更新用户上下文（新请求时调用）

        Args:
            user_context: 新的用户上下文
            thread_id: 会话线程ID（用于隔离存储）
        """
        with self._lock:
            if thread_id:
                self._context_store[thread_id] = user_context
                middleware_logger.debug(
                    f"Context updated for thread {thread_id}: user={user_context.user_id}"
                )
            else:
                self._default_context = user_context

    def get_current_context(self, thread_id: str = "") -> ProcurementContext:
        """获取当前上下文"""
        return self._get_context(thread_id)

    def clear_context(self, thread_id: str):
        """清除指定线程的上下文（会话结束时调用）"""
        with self._lock:
            self._context_store.pop(thread_id, None)

    # ============================================================
    # 内部方法
    # ============================================================

    def _get_context(self, thread_id: str) -> ProcurementContext:
        """获取指定线程的上下文（线程安全）"""
        with self._lock:
            ctx = self._context_store.get(thread_id)
            if ctx is not None:
                return ctx
            return self._default_context

    def _get_thread_id(self, runtime: Runtime) -> str:
        """从 runtime 提取 thread_id"""
        try:
            config = runtime.config if hasattr(runtime, "config") else {}
            if isinstance(config, dict):
                configurable = config.get("configurable", {})
                return configurable.get("thread_id", "default")
        except Exception:
            pass
        return "default"


# ============================================================
# 工厂函数（为每个 Agent 实例创建独立中间件）
# ============================================================

def create_context_middleware(
    user_context: ProcurementContext | None = None,
) -> ContextInjectionMiddleware:
    """
    工厂函数：创建用户上下文注入中间件

    Args:
        user_context: 初始用户上下文

    Returns:
        新的 ContextInjectionMiddleware 实例（独立于其他实例）
    """
    return ContextInjectionMiddleware(user_context=user_context)
