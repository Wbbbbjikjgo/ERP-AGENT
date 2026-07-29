"""
中间件 3: 本地技能同步到沙箱
增量同步 src/skills/ → 沙箱 /skills/{scope}/（hash 比对）.
"""
import hashlib
import os
from pathlib import Path
from typing import Any

from langchain.agents.middleware import AgentMiddleware, Runtime
from ..log_utils import middleware_logger


class SkillsSyncMiddleware(AgentMiddleware):
    """
    技能同步中间件

    职责：
    - 首次执行时将本地 src/skills/ 目录同步到沙箱 /skills/
    - 使用文件 hash 比对实现增量同步（仅传输变更文件）
    - 同步范围：SKILL.md + 附带的 .py 脚本

    开发模式（LocalShellBackend）：
    - 本地执行无需同步，仅校验技能文件完整性
    """

    def __init__(self, skills_dir: str | Path | None = None, sandbox_backend=None):
        self._skills_dir = Path(skills_dir) if skills_dir else None
        self._sandbox_backend = sandbox_backend
        self._file_hashes: dict[str, str] = {}
        self._synced = False
        self.tools = []

    @property
    def name(self) -> str:
        return "SkillsSyncMiddleware"

    def before_agent(self, state: Any, runtime: Runtime) -> dict[str, Any] | None:
        """首次执行时同步技能文件"""
        if self._synced:
            return None

        if self._skills_dir and self._skills_dir.exists():
            if self._sandbox_backend is not None:
                # 生产模式：同步到沙箱容器
                self._sync_to_sandbox()
            else:
                # 开发模式：仅校验完整性
                self._validate_local_skills()

        self._synced = True
        return None

    def _validate_local_skills(self):
        """校验本地技能文件完整性"""
        skill_count = 0
        for skill_md in self._skills_dir.rglob("SKILL.md"):
            skill_count += 1
            # 验证 frontmatter 存在
            content = skill_md.read_text(encoding="utf-8")
            if not content.startswith("---"):
                middleware_logger.warning(f"Skill missing frontmatter: {skill_md}")
        middleware_logger.info(f"Skills validated: {skill_count} skills found in {self._skills_dir}")

    def _sync_to_sandbox(self):
        """增量同步技能到沙箱"""
        synced_count = 0
        for file_path in self._skills_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix in (".md", ".py"):
                rel_path = file_path.relative_to(self._skills_dir)
                file_hash = self._compute_hash(file_path)

                # 仅同步变更文件
                if self._file_hashes.get(str(rel_path)) != file_hash:
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        remote_path = f"/skills/{rel_path}"
                        self._sandbox_backend.write_file(remote_path, content)
                        self._file_hashes[str(rel_path)] = file_hash
                        synced_count += 1
                    except Exception as e:
                        middleware_logger.error(f"Failed to sync {rel_path}: {e}")

        if synced_count > 0:
            middleware_logger.info(f"Skills synced to sandbox: {synced_count} files updated")

    @staticmethod
    def _compute_hash(file_path: Path) -> str:
        """计算文件 MD5 hash"""
        return hashlib.md5(file_path.read_bytes()).hexdigest()
