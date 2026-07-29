"""
中间件 3: 本地技能同步到沙箱（完整文件夹级增量同步）

核心修复：
1. 使用相对路径（而非文件名）作为哈希 key，避免同名文件冲突
2. 保留完整子目录结构同步到沙箱 /skills/
3. 每次 Agent 执行前增量同步（hash 比对变更文件）
4. 处理远程已删除文件的清理
5. 以 skill 文件夹为单位计算整体哈希（含脚本和依赖）

Skill 标准结构：
  skills/
    procurement/
      web-scraper/
        SKILL.md
        scraper.py
        requirements.txt
      procurement-analysis/
        SKILL.md
"""
import hashlib
import os
from pathlib import Path
from typing import Any

from langchain.agents.middleware import AgentMiddleware, Runtime
from ..log_utils import middleware_logger


class SkillsSyncMiddleware(AgentMiddleware):
    """
    技能同步中间件（Harness — 完整文件夹级增量同步）

    职责：
    - 每次 Agent 执行前增量同步 src/skills/ → 沙箱 /skills/
    - 使用文件相对路径的 MD5 hash 实现精准增量同步
    - 保留完整目录结构（子目录不丢失）
    - 检测并清理沙箱中已被本地删除的文件
    - 以 skill 文件夹为单位校验完整性

    开发模式（LocalShellBackend）：
    - 本地执行无需同步，仅校验技能文件完整性
    """

    def __init__(self, skills_dir: str | Path | None = None, sandbox_backend=None):
        self._skills_dir = Path(skills_dir) if skills_dir else None
        self._sandbox_backend = sandbox_backend
        # 文件级哈希缓存：relative_path → file_md5
        self._file_hashes: dict[str, str] = {}
        # 上一次同步的文件集合（用于检测删除）
        self._last_synced_files: set[str] = set()
        # 是否已完成首次同步
        self._first_sync_done = False
        self.tools = []

    @property
    def name(self) -> str:
        return "SkillsSyncMiddleware"

    def before_agent(self, state: Any, runtime: Runtime) -> dict[str, Any] | None:
        """
        每次 Agent 执行前增量同步技能文件

        - 首次执行：完整同步
        - 后续执行：仅同步变更文件（hash 比对）
        - 检测并清理已删除文件
        """
        if not self._skills_dir or not self._skills_dir.exists():
            return None

        if self._sandbox_backend is not None:
            # 生产模式：增量同步到沙箱
            self._sync_to_sandbox()
        else:
            # 开发模式：仅校验完整性
            self._validate_local_skills()

        return None

    def _validate_local_skills(self):
        """校验本地技能文件完整性"""
        skill_count = 0
        for skill_md in self._skills_dir.rglob("SKILL.md"):
            skill_count += 1
            skill_dir = skill_md.parent
            # 验证 skill 目录结构
            has_scripts = any(skill_dir.glob("*.py"))
            has_deps = (skill_dir / "requirements.txt").exists()
            middleware_logger.debug(
                f"Skill validated: {skill_dir.name} "
                f"(scripts={has_scripts}, deps={has_deps})"
            )
        middleware_logger.info(
            f"Skills validated: {skill_count} skills in {self._skills_dir}"
        )

    def _sync_to_sandbox(self):
        """
        增量同步技能文件到沙箱

        算法：
        1. 扫描本地 skills 目录，获取所有文件及其相对路径
        2. 计算每个文件的 MD5 哈希
        3. 与缓存比对，仅上传变更的文件
        4. 检测本地已删除的文件，从沙箱中清除
        5. 更新哈希缓存
        """
        if not self._sandbox_backend:
            return

        # 扫描本地文件
        current_files: dict[str, str] = {}  # rel_path → hash
        for file_path in self._skills_dir.rglob("*"):
            if file_path.is_file() and not self._should_skip(file_path):
                rel_path = str(file_path.relative_to(self._skills_dir))
                file_hash = self._compute_hash(file_path)
                current_files[rel_path] = file_hash

        current_file_set = set(current_files.keys())

        # === 增量上传变更文件 ===
        uploaded = 0
        for rel_path, file_hash in current_files.items():
            if self._file_hashes.get(rel_path) != file_hash:
                try:
                    file_path = self._skills_dir / rel_path
                    # 文本文件读取为 str，二进制文件跳过
                    if self._is_text_file(file_path):
                        content = file_path.read_text(encoding="utf-8")
                    else:
                        content = file_path.read_bytes()

                    remote_path = f"/skills/{rel_path}"
                    self._sandbox_backend.write_file(remote_path, content)
                    uploaded += 1
                except Exception as e:
                    middleware_logger.error(f"Failed to sync {rel_path}: {e}")

        # === 清理已删除的文件 ===
        deleted = 0
        removed_files = self._last_synced_files - current_file_set
        for rel_path in removed_files:
            try:
                remote_path = f"/skills/{rel_path}"
                self._sandbox_backend.rm(remote_path)
                deleted += 1
            except Exception as e:
                middleware_logger.warning(f"Failed to remove {rel_path}: {e}")

        # === 更新缓存 ===
        self._file_hashes.update(current_files)
        # 移除已删除文件的缓存
        for rel_path in removed_files:
            self._file_hashes.pop(rel_path, None)
        self._last_synced_files = current_file_set
        self._first_sync_done = True

        # 日志
        if uploaded > 0 or deleted > 0:
            middleware_logger.info(
                f"Skills synced: {uploaded} uploaded, {deleted} deleted "
                f"(total: {len(current_files)} files)"
            )
        elif not self._first_sync_done:
            middleware_logger.info(
                f"Skills sync: {len(current_files)} files (no changes)"
            )

    def _should_skip(self, file_path: Path) -> bool:
        """判断是否跳过文件"""
        skip_patterns = {
            "__pycache__", ".pyc", ".pyo", ".git", ".DS_Store",
            "node_modules", ".egg-info",
        }
        name = file_path.name
        return any(pat in name for pat in skip_patterns)

    @staticmethod
    def _is_text_file(file_path: Path) -> bool:
        """判断是否为文本文件"""
        text_extensions = {
            ".md", ".txt", ".py", ".yaml", ".yml", ".json",
            ".csv", ".toml", ".cfg", ".ini", ".sh", ".bash",
            ".js", ".ts", ".html", ".css", ".xml", ".rst",
        }
        return file_path.suffix.lower() in text_extensions

    @staticmethod
    def _compute_hash(file_path: Path) -> str:
        """计算文件 MD5 hash"""
        return hashlib.md5(file_path.read_bytes()).hexdigest()

    def compute_skill_folder_hash(self, skill_dir: Path) -> str:
        """
        计算整个 skill 文件夹的哈希值（用于判断 skill 是否有变更）

        将文件夹内所有文件的哈希拼接后再哈希，作为整个 skill 的指纹。
        """
        if not skill_dir.is_dir():
            return ""
        folder_hash = hashlib.md5()
        for file_path in sorted(skill_dir.rglob("*")):
            if file_path.is_file() and not self._should_skip(file_path):
                rel = str(file_path.relative_to(skill_dir))
                file_hash = self._compute_hash(file_path)
                folder_hash.update(f"{rel}:{file_hash}".encode())
        return folder_hash.hexdigest()

    def invalidate(self):
        """手动失效缓存，强制下次完整同步（新 Skill 安装后调用）"""
        self._file_hashes.clear()
        self._last_synced_files.clear()
        self._first_sync_done = False
        middleware_logger.info("SkillsSync cache invalidated, will full sync next time")
