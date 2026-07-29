"""
中间件 1: 沙箱健康检查 + 自动恢复
在每次 Agent 执行前 ping 沙箱，不可达时触发重建.
"""
import asyncio
import time
from typing import Any

from langchain.agents.middleware import AgentMiddleware, Runtime
from ..log_utils import middleware_logger


class SandboxHealthMiddleware(AgentMiddleware):
    """
    沙箱健康检查中间件

    生产环境逻辑：
    - before_agent: ping 沙箱容器（docker inspect / exec echo）
    - 不可达 → 调用 sandbox_manager.rebuild() 重建
    - 记录健康状态到 state 供其他中间件使用

    开发模式（LocalShellBackend）：
    - 始终视为健康，仅记录心跳时间
    """

    def __init__(self, sandbox_manager=None, check_interval: float = 60.0):
        self._sandbox_manager = sandbox_manager
        self._check_interval = check_interval
        self._last_check: float = 0
        self._healthy: bool = True
        self._consecutive_failures: int = 0
        self.tools = []

    @property
    def name(self) -> str:
        return "SandboxHealthMiddleware"

    def before_agent(self, state: Any, runtime: Runtime) -> dict[str, Any] | None:
        """Agent 执行前检查沙箱健康状态"""
        now = time.time()

        # 限频：避免每次调用都检查
        if now - self._last_check < self._check_interval:
            return None

        self._last_check = now

        if self._sandbox_manager is None:
            # 开发模式：LocalShellBackend 始终健康
            self._healthy = True
            return None

        # 生产模式：检查沙箱容器
        try:
            is_alive = self._ping_sandbox()
            if is_alive:
                self._healthy = True
                self._consecutive_failures = 0
                middleware_logger.debug("Sandbox health check: OK")
            else:
                self._consecutive_failures += 1
                middleware_logger.warning(
                    f"Sandbox health check FAILED ({self._consecutive_failures} consecutive)"
                )
                if self._consecutive_failures >= 2:
                    middleware_logger.info("Attempting sandbox rebuild...")
                    self._sandbox_manager.rebuild()
                    self._consecutive_failures = 0
                    self._healthy = True
        except Exception as e:
            middleware_logger.error(f"Sandbox health check error: {e}")
            self._healthy = False

        return None

    def _ping_sandbox(self) -> bool:
        """Ping 沙箱容器，返回是否存活"""
        if self._sandbox_manager is None:
            return True
        try:
            container_id = self._sandbox_manager.get_active_container()
            if not container_id:
                return False
            # 使用 docker exec 检测
            import docker
            client = docker.from_env()
            container = client.containers.get(container_id)
            exit_code, _ = container.exec_run("echo ok", timeout=5)
            return exit_code == 0
        except Exception:
            return False
