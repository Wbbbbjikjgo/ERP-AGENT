"""
技能分配工具
下载 → 创建 → 测试 → 分配 → 持久化
"""
import os
import shutil
from pathlib import Path
from langchain_core.tools import tool

from ..log_utils import agent_logger

SKILLS_BASE_DIR = Path(__file__).parent.parent.parent / "skills"


@tool
def assign_skill(skill_name: str, agent_name: str = "main") -> str:
    """将技能分配给指定的 Agent。

    Args:
        skill_name: 技能名称（目录名），例如 "procurement-analysis"
        agent_name: 目标Agent名称，"main" 表示主Agent，其他为子Agent名称

    Returns:
        分配结果描述
    """
    # 查找技能目录
    skill_path = None
    for scope_dir in SKILLS_BASE_DIR.iterdir():
        if scope_dir.is_dir():
            candidate = scope_dir / skill_name
            if candidate.exists() and (candidate / "SKILL.md").exists():
                skill_path = candidate
                break

    if skill_path is None:
        # 也检查直接在 scope 下的 .md 文件
        for scope_dir in SKILLS_BASE_DIR.iterdir():
            if scope_dir.is_dir():
                candidate = scope_dir / f"{skill_name}.md"
                if candidate.exists():
                    skill_path = candidate
                    break

    if skill_path is None:
        available = []
        for scope_dir in SKILLS_BASE_DIR.iterdir():
            if scope_dir.is_dir():
                for item in scope_dir.iterdir():
                    if item.is_dir() and (item / "SKILL.md").exists():
                        available.append(item.name)
        return f"技能 '{skill_name}' 未找到。可用技能: {', '.join(available)}"

    # 如果目标是子Agent，复制到对应 scope
    if agent_name != "main":
        target_dir = SKILLS_BASE_DIR / agent_name / skill_name
        if not target_dir.exists():
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            if skill_path.is_dir():
                shutil.copytree(skill_path, target_dir)
            else:
                shutil.copy2(skill_path, target_dir / skill_path.name)
            agent_logger.info(f"Skill '{skill_name}' assigned to agent '{agent_name}'")
            return f"技能 '{skill_name}' 已成功分配给 Agent '{agent_name}'"
        else:
            return f"技能 '{skill_name}' 已存在于 Agent '{agent_name}' 中"

    agent_logger.info(f"Skill '{skill_name}' verified for main agent")
    return f"技能 '{skill_name}' 已在主 Agent 技能库中可用"
