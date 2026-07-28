"""
沙箱生命周期管理
五态：预热池 → 认领 → MongoDB缓存 → 新建 → 销毁
用户作用域隔离（user_id → container_id 映射）
"""
from typing import Dict, Optional
from .custom_opensandbox import CustomOpenSandbox
from .sandbox_setup import create_and_setup_sandbox
from ..log_utils import sandbox_logger


class SandboxManager:
    """沙箱生命周期管理器"""

    _instance: Optional['SandboxManager'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        # user_id → sandbox 映射
        self._user_sandboxes: Dict[str, CustomOpenSandbox] = {}
        # 预热池
        self._warm_pool: list = []
        sandbox_logger.info("SandboxManager initialized")

    def get_sandbox(self, user_id: str) -> CustomOpenSandbox:
        """获取用户的沙箱实例（不存在则创建）"""
        if user_id in self._user_sandboxes:
            sandbox = self._user_sandboxes[user_id]
            if sandbox.ping():
                return sandbox
            else:
                # 沙箱不可达，重建
                sandbox_logger.warning(f"Sandbox unhealthy for user {user_id}, rebuilding...")
                del self._user_sandboxes[user_id]

        # 创建新沙箱
        sandbox = create_and_setup_sandbox(user_id)
        self._user_sandboxes[user_id] = sandbox
        return sandbox

    def get_active_container(self, user_id: str = "default_user") -> Optional[str]:
        """获取用户当前活跃的容器ID（供健康检查使用）"""
        sandbox = self._user_sandboxes.get(user_id)
        if sandbox:
            return sandbox.container_id
        return None

    def rebuild(self, user_id: str = "default_user") -> CustomOpenSandbox:
        """重建用户沙箱"""
        if user_id in self._user_sandboxes:
            try:
                self._user_sandboxes[user_id].destroy()
            except Exception:
                pass
            del self._user_sandboxes[user_id]
        return self.get_sandbox(user_id)

    def destroy_user_sandbox(self, user_id: str):
        """销毁用户沙箱"""
        if user_id in self._user_sandboxes:
            self._user_sandboxes[user_id].destroy()
            del self._user_sandboxes[user_id]
            sandbox_logger.info(f"Sandbox destroyed for user: {user_id}")

    def destroy_all(self):
        """销毁所有沙箱"""
        for user_id, sandbox in self._user_sandboxes.items():
            sandbox.destroy()
        self._user_sandboxes.clear()
        sandbox_logger.info("All sandboxes destroyed")


# 全局单例
sandbox_manager = SandboxManager()
