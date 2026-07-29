"""
中间件 4: 持久化技能恢复
从 StoreBackend 恢复用户持久化的自定义技能到沙箱.
"""
from typing import Any

from langchain.agents.middleware import AgentMiddleware, Runtime
from ..log_utils import middleware_logger


class UserSkillsRestoreMiddleware(AgentMiddleware):
    """
    持久化技能恢复中间件

    职责：
    - Agent 启动时从 StoreBackend (/persisted-skills/) 读取用户自定义技能
    - 将技能文件恢复到沙箱 /skills/ 目录
    - 确保跨会话技能持久性（用户通过 assign_skill 安装的技能不会丢失）

    工作流程：
    1. store.aget(namespace=("persisted-skills", user_id)) → 技能清单
    2. 逐个读取技能内容 → 写入沙箱
    3. 记录恢复结果
    """

    def __init__(self, store=None, user_id: str = "default_user", sandbox_backend=None):
        self._store = store
        self._user_id = user_id
        self._sandbox_backend = sandbox_backend
        self._restored = False
        self.tools = []

    @property
    def name(self) -> str:
        return "UserSkillsRestoreMiddleware"

    def before_agent(self, state: Any, runtime: Runtime) -> dict[str, Any] | None:
        """首次执行时恢复持久化技能"""
        if self._restored:
            return None

        if self._store is not None and self._sandbox_backend is not None:
            self._restore_skills()

        self._restored = True
        return None

    def _restore_skills(self):
        """从 Store 恢复技能到沙箱"""
        try:
            import asyncio
            # 从 store 获取技能索引
            namespace = ("persisted-skills", self._user_id)
            # 使用同步方式尝试获取（store 可能支持同步）
            items = self._store.search(namespace)
            restored_count = 0

            for item in items:
                skill_name = item.key
                skill_content = item.value.get("content", "")
                skill_path = item.value.get("path", f"/skills/custom/{skill_name}")

                if skill_content:
                    self._sandbox_backend.write_file(skill_path, skill_content)
                    restored_count += 1

            if restored_count > 0:
                middleware_logger.info(
                    f"Restored {restored_count} persisted skills for user {self._user_id}"
                )
        except Exception as e:
            middleware_logger.warning(f"Skills restore failed (non-critical): {e}")
