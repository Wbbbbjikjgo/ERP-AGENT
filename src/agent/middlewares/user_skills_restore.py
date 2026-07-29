"""
中间件 4: 持久化技能恢复（增量同步 + 完整错误处理）
从 StoreBackend 恢复用户持久化的自定义技能到沙箱.

修复的 6 个问题：
1. search() 空值保护（用户无持久化技能时不报错）
2. 恢复时先创建父目录（避免 write_file 因目录不存在失败）
3. 移除 _restored 单例标记（每次请求都尝试增量恢复）
4. 恢复失败时使用 error 级别日志（不是 non-critical warning）
5. 同名技能覆盖保护（先备份再写入）
6. 增量同步（hash 比对，跳过未变更的文件）
"""
import hashlib
from typing import Any, Dict

from langchain.agents.middleware import AgentMiddleware, Runtime
from ..log_utils import middleware_logger


class UserSkillsRestoreMiddleware(AgentMiddleware):
    """
    持久化技能恢复中间件（增量同步 + 完整错误处理）

    职责：
    - Agent 启动时从 StoreBackend (/persisted-skills/) 读取用户自定义技能
    - 将技能文件恢复到沙箱 /skills/custom/ 目录
    - 确保跨会话技能持久性（用户通过 assign_skill 安装的技能不会丢失）
    - 增量同步：hash 比对，仅恢复变更的文件

    工作流程：
    1. store.search(namespace=("persisted-skills", user_id)) → 技能清单
    2. 逐个读取技能内容 → hash 比对 → 增量写入沙箱
    3. 记录恢复结果
    """

    def __init__(self, store=None, user_id: str = "default_user", sandbox_backend=None):
        self._store = store
        self._user_id = user_id
        self._sandbox_backend = sandbox_backend
        # 文件级哈希缓存：skill_path → hash
        self._restored_hashes: Dict[str, str] = {}
        # 已恢复的技能集合（用于检测删除）
        self._restored_skills: set = set()
        self.tools = []

    @property
    def name(self) -> str:
        return "UserSkillsRestoreMiddleware"

    def before_agent(self, state: Any, runtime: Runtime) -> dict[str, Any] | None:
        """
        每次 Agent 执行前尝试增量恢复持久化技能

        不使用 _restored 标记：
        - 每次请求都检查 store 中是否有新增/变更的技能
        - 通过 hash 比对实现增量同步
        - 新持久化的技能会被自动发现和恢复
        """
        if self._store is None or self._sandbox_backend is None:
            return None

        self._restore_skills()
        return None

    def _restore_skills(self):
        """从 Store 增量恢复技能到沙箱"""
        try:
            # === 1. 从 store 获取技能清单（空值保护）===
            namespace = ("persisted-skills", self._user_id)
            try:
                items = self._store.search(namespace)
            except Exception as e:
                middleware_logger.error(
                    f"Failed to search persisted skills: {e}"
                )
                return

            # 空值保护：store 返回 None 或空列表
            if not items:
                middleware_logger.debug(
                    f"No persisted skills for user {self._user_id}"
                )
                return

            restored_count = 0
            skipped_count = 0
            current_skills = set()

            for item in items:
                # 安全获取属性（兼容不同 store 实现）
                try:
                    skill_key = getattr(item, "key", None)
                    skill_value = getattr(item, "value", None)

                    if not skill_key or not skill_value:
                        continue

                    if not isinstance(skill_value, dict):
                        continue

                    skill_content = skill_value.get("content", "")
                    skill_path = skill_value.get(
                        "path", f"/skills/custom/{skill_key}"
                    )

                    if not skill_content:
                        continue

                    current_skills.add(skill_key)

                    # === 2. 增量同步（hash 比对）===
                    content_hash = hashlib.md5(
                        skill_content.encode("utf-8") if isinstance(skill_content, str)
                        else skill_content
                    ).hexdigest()

                    if self._restored_hashes.get(skill_path) == content_hash:
                        skipped_count += 1
                        continue  # 未变更，跳过

                    # === 3. 创建父目录 ===
                    try:
                        dir_path = "/".join(skill_path.rstrip("/").split("/")[:-1])
                        if dir_path:
                            self._sandbox_backend.execute(f"mkdir -p '{dir_path}'")
                    except Exception as e:
                        middleware_logger.error(
                            f"Failed to create directory for {skill_path}: {e}"
                        )
                        continue

                    # === 4. 同名覆盖保护 ===
                    if self._sandbox_backend.file_exists(skill_path):
                        # 备份已有文件
                        backup_path = f"{skill_path}.bak"
                        try:
                            self._sandbox_backend.cp(skill_path, backup_path)
                            middleware_logger.debug(
                                f"Backed up existing skill: {skill_path} -> {backup_path}"
                            )
                        except Exception:
                            pass  # 备份失败不阻塞恢复

                    # === 5. 写入文件 ===
                    self._sandbox_backend.write_file(skill_path, skill_content)
                    self._restored_hashes[skill_path] = content_hash
                    restored_count += 1

                except Exception as e:
                    middleware_logger.error(
                        f"Failed to restore skill '{getattr(item, 'key', 'unknown')}': {e}"
                    )

            # === 6. 日志汇总 ===
            self._restored_skills = current_skills

            if restored_count > 0:
                middleware_logger.info(
                    f"Restored {restored_count} persisted skills for user {self._user_id} "
                    f"(skipped {skipped_count} unchanged)"
                )
            elif skipped_count > 0:
                middleware_logger.debug(
                    f"All persisted skills up to date for {self._user_id} "
                    f"({skipped_count} skills, 0 changes)"
                )

        except Exception as e:
            # 使用 error 级别日志（技能丢失是功能性故障）
            middleware_logger.error(
                f"Skills restore failed for user {self._user_id}: {e}",
                exc_info=True,
            )

    def invalidate(self):
        """手动失效缓存，强制下次完整恢复"""
        self._restored_hashes.clear()
        self._restored_skills.clear()
        middleware_logger.info("UserSkillsRestore cache invalidated")

    def get_restored_skills(self) -> set:
        """获取已恢复的技能集合"""
        return set(self._restored_skills)
