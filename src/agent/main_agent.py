"""
主入口：create_main_agent() + precompute_agent_context()
DeepAgent 核心组装 — 严格遵循 Harness Engineering 架构
"""
import os
import io
import tarfile
import fnmatch
from typing import Optional
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StoreBackend, LocalShellBackend
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
)

from .backends.custom_opensandbox import DockerSandboxBackend

from .config import (
    get_llm, MONGODB_URI, MONGODB_DB_NAME,
    SKILLS_STORE_NAMESPACE, INTERRUPT_ON_TOOLS,
    MAX_MODEL_CALLS, MAX_TOOL_CALLS,
)
from .schema import ProcurementContext
from .log_utils import agent_logger
from .memory.prompts import MAIN_SYSTEM_PROMPT

# 项目路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
SKILLS_DIR = PROJECT_ROOT / "src" / "skills"
MEMORY_DIR = Path(__file__).parent / "memory"


def _upload_project_to_sandbox(sandbox):
    """
    将项目文件上传到沙箱 /workspace/src/ 目录，搭建 1:1 开发环境。
    跳过 node_modules / .git / __pycache__ / .next 等无关目录。
    """
    skip_patterns = [
        ".git", "__pycache__", "node_modules", ".next", ".venv",
        ".eggs", "*.pyc", "*.pyo", ".DS_Store", ".docker",
        "*.png", "*.jpg", "*.jpeg", "*.gif",  # 生成物不传
    ]

    def _should_skip(rel_path: str) -> bool:
        for pattern in skip_patterns:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
            parts = rel_path.replace("\\", "/").split("/")
            for part in parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
        return False

    remote_dir = "/workspace/src"
    try:
        sandbox.execute(f"mkdir -p '{remote_dir}'")

        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w:gz") as tar:
            for file_path in sorted(PROJECT_ROOT.rglob("*")):
                if not file_path.is_file():
                    continue
                rel = str(file_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
                if _should_skip(rel):
                    continue
                tar.add(str(file_path), arcname=rel)

        tar_stream.seek(0)
        data = tar_stream.read()

        # 分块上传（tar 流一次性写入）
        sandbox._container.put_archive(remote_dir, data)

        # 获取文件数量和总大小
        count_result = sandbox.execute(
            f"find {remote_dir} -type f 2>/dev/null | wc -l"
        )
        size_result = sandbox.execute(
            f"du -sh {remote_dir} 2>/dev/null | cut -f1"
        )
        file_count = count_result.output.strip() if count_result.exit_code == 0 else "?"
        total_size = size_result.output.strip() if size_result.exit_code == 0 else "?"

        agent_logger.info(
            f"Project uploaded to sandbox: {remote_dir} "
            f"({file_count} files, {total_size})"
        )
        return True
    except Exception as e:
        agent_logger.warning(f"Project upload to sandbox failed (non-fatal): {e}")
        return False


def _load_skills_prompt(skills_dir: Path) -> str:
    """
    手动加载所有 SKILL.md 文件内容，拼接为提示词段落。
    解决框架内置 skills 加载器无法解析含中文/空格路径的问题。
    """
    if not skills_dir.exists():
        return ""

    skill_sections = []
    for skill_md in sorted(skills_dir.rglob("SKILL.md")):
        try:
            content = skill_md.read_text(encoding="utf-8").strip()
            if content:
                # 用相对路径作为技能标识
                rel_path = str(skill_md.relative_to(skills_dir))
                skill_sections.append(f"### Skill: {rel_path}\n{content}")
        except Exception as e:
            agent_logger.warning(f"Failed to load skill {skill_md}: {e}")

    # 也加载独立的 .md 技能文件（非 SKILL.md）
    for md_file in sorted(skills_dir.rglob("*.md")):
        if md_file.name == "SKILL.md":
            continue  # 已处理
        try:
            content = md_file.read_text(encoding="utf-8").strip()
            if content and len(content) > 20:
                rel_path = str(md_file.relative_to(skills_dir))
                skill_sections.append(f"### Skill: {rel_path}\n{content}")
        except Exception:
            pass

    if not skill_sections:
        return ""

    # 构建技能摘要列表（name + description）
    import re as _re
    skill_summary = []
    for section in skill_sections:
        name_match = _re.search(r"name: (\S+)", section)
        desc_match = _re.search(r"description: (.+)", section)
        name = name_match.group(1) if name_match else "?"
        desc = desc_match.group(1) if desc_match else ""
        if name not in ("skill-name", "str", "?"):
            skill_summary.append(f"- **{name}**: {desc}")

    summary_block = "\n".join(skill_summary) if skill_summary else ""

    return (
        "\n\n---\n\n"
        "## 可用技能 (Skills)\n\n"
        "以下技能已加载到沙箱 **/skills/** 目录和 **/src/skills/** 目录，可通过沙箱执行：\n\n"
        + (summary_block + "\n\n---\n\n" if summary_block else "")
        + "\n\n".join(skill_sections)
    )


async def precompute_agent_context(
    user_id: str = "default_user",
    username: str = "用户",
    store=None,
) -> ProcurementContext:
    """
    预计算 Agent 上下文

    从 Store 加载用户历史偏好，构造完整的 ProcurementContext。
    如果 Store 不可用则使用默认值。
    """
    preferences = {}

    if store is not None:
        try:
            namespace = ("user-preferences", user_id)
            items = store.search(namespace)
            for item in items:
                if item.key == "preferences" and isinstance(item.value, dict):
                    preferences.update(item.value)
            if preferences:
                agent_logger.info(f"Loaded preferences for {user_id}: {list(preferences.keys())}")
        except Exception as e:
            agent_logger.warning(f"Failed to load preferences: {e}")

    return ProcurementContext(
        user_id=user_id,
        username=username,
        preferences=preferences,
    )


def create_main_agent(
    user_context: Optional[ProcurementContext] = None,
    checkpointer=None,
    store=None,
):
    """
    创建主 Agent 实例

    组装顺序（严格遵循文档）：
    1. LLM（通义千问 qwen-plus）
    2. CompositeBackend 三层路由（default=sandbox, /memories/=Store, /persisted-skills/=Store）
    3. 工具加载（MCP + chart + web_search + hitl）
    4. 子Agent配置（YAML声明式）
    5. 中间件栈（7自定义 + 框架内置）
    6. 创建 Agent

    Args:
        user_context: 用户上下文（含偏好）
        checkpointer: LangGraph checkpointer（会话持久化）
        store: LangGraph store（跨会话存储）

    Returns:
        CompiledStateGraph - 可执行的 Agent 图
    """
    if user_context is None:
        user_context = ProcurementContext()

    agent_logger.info(f"Creating main agent for user: {user_context.user_id}")

    # ===== 1. LLM =====
    llm = get_llm()

    # ===== 2. Backend - CompositeBackend 三层路由 =====
    # 默认后端：Docker 沙箱（代码执行隔离），连接失败时回退到 LocalShell
    try:
        sandbox_backend = DockerSandboxBackend(container_name="erp-sandbox")
        agent_logger.info("Using Docker sandbox backend (erp-sandbox)")

        # ===== 沙箱初始化：创建目录 + 上传项目文件 =====
        # ⚡ 注意：依赖包（matplotlib/numpy/pandas）在 chart_generator 中按需安装
        # 不在初始化时阻塞安装，避免 Agent 启动超时
        try:
            sandbox_backend.execute(
                "mkdir -p /workspace/charts /workspace/output /workspace/data /skills /src/skills"
            )
            agent_logger.info("Sandbox directories created")

            # 上传整个项目文件到沙箱 /workspace/src/（1:1 开发环境）
            _upload_project_to_sandbox(sandbox_backend)

            # 将技能文件同步到常用路径，确保 agent 能通过 /src/skills/ 找到
            sandbox_backend.execute(
                "cp -r /workspace/src/src/skills/* /src/skills/ 2>/dev/null || true"
            )
            sandbox_backend.execute(
                "cp -r /workspace/src/src/skills/* /skills/ 2>/dev/null || true"
            )
            agent_logger.info("Skills synced to /skills/ and /src/skills/ in sandbox")
        except Exception as init_err:
            agent_logger.warning(f"Sandbox initialization error (non-fatal): {init_err}")

        # ✅ 注册沙箱到全局持有器，让所有工具能访问沙箱
        from .backends.sandbox_holder import set_sandbox
        set_sandbox(sandbox_backend)
    except Exception as e:
        agent_logger.warning(f"Docker sandbox unavailable ({e}), falling back to LocalShell")
        sandbox_backend = LocalShellBackend(virtual_mode=True)

    def backend_factory(rt):
        """后端工厂：根据路径路由到不同后端"""
        routes = {}
        if store is not None:
            routes["/memories/"] = StoreBackend(
                namespace=lambda _rt: (user_context.user_id,),
            )
            routes["/persisted-skills/"] = StoreBackend(
                namespace=lambda _rt: SKILLS_STORE_NAMESPACE,
            )
        return CompositeBackend(
            default=sandbox_backend,
            routes=routes,
        )

    # ===== 3. 加载工具 =====
    from .tools.mcp_client import load_mcp_tools_sync
    from .tools.chart_generator import generate_chart
    from .tools.web_search import web_search
    from .tools.web_fetch import web_fetch, install_skill
    from .tools.hitl_tools import request_order_info
    from .tools.download_sandbox_file import download_sandbox_file, list_sandbox_files
    from .tools.document_generator import generate_document, generate_table_report

    mcp_tools = load_mcp_tools_sync()
    custom_tools = [generate_chart, web_search, web_fetch, install_skill, request_order_info,
                    download_sandbox_file, list_sandbox_files,
                    generate_document, generate_table_report]
    all_tools = mcp_tools + custom_tools

    agent_logger.info(
        f"Tools loaded: {len(mcp_tools)} MCP + {len(custom_tools)} custom = {len(all_tools)} total"
    )

    # ===== 4. 加载子Agent配置 =====
    from .subagents.loader import load_subagent_configs, resolve_subagent_tools, get_delegation_context_prompt
    subagent_configs = load_subagent_configs()
    subagents = resolve_subagent_tools(subagent_configs, all_tools)
    # 生成委派上下文协议（注入主 Agent 提示词）
    delegation_prompt = get_delegation_context_prompt(subagent_configs)

    # ===== 5. 组装中间件栈 =====
    # 自定义中间件
    from .middlewares.sandbox_health import SandboxHealthMiddleware
    from .middlewares.context_injection import ContextInjectionMiddleware
    from .middlewares.skills_sync import SkillsSyncMiddleware
    from .middlewares.user_skills_restore import UserSkillsRestoreMiddleware
    from .middlewares.tools_summarization import ToolsSummarizationMiddleware
    from .middlewares.memory_update import MemoryUpdateMiddleware
    from .middlewares.sandbox_breaker import SandboxCircuitBreakerMiddleware

    # 注意：create_deep_agent 内部已自动添加：
    # - SummarizationMiddleware（自动摘要 + compact_conversation 工具）
    # - FilesystemMiddleware, SkillsMiddleware, SubAgentMiddleware
    # - TodoListMiddleware, PatchToolCallsMiddleware, MemoryMiddleware
    # 我们只需添加自定义中间件 + 调用限制
    middlewares = [
        # --- 自定义中间件（执行顺序 1→7）---
        SandboxHealthMiddleware(),                                    # 1. 沙箱健康检查
        ContextInjectionMiddleware(user_context=user_context),        # 2. 用户上下文注入
        SkillsSyncMiddleware(skills_dir=SKILLS_DIR, sandbox_backend=sandbox_backend),  # 3. 技能同步
        UserSkillsRestoreMiddleware(store=store, user_id=user_context.user_id),  # 4. 技能恢复
        ToolsSummarizationMiddleware(),                               # 5. 摘要监控
        MemoryUpdateMiddleware(store=store, user_id=user_context.user_id),      # 6. 偏好提取
        SandboxCircuitBreakerMiddleware(failure_threshold=3, recovery_timeout=60),  # 7. 熔断器
        # --- 框架内置中间件（调用限制）---
        ModelCallLimitMiddleware(run_limit=MAX_MODEL_CALLS),          # 模型调用上限
        ToolCallLimitMiddleware(run_limit=MAX_TOOL_CALLS),            # 工具调用上限
    ]

    # ===== 6. 构建系统提示词 =====
    system_prompt = MAIN_SYSTEM_PROMPT.format(
        user_id=user_context.user_id,
        username=user_context.username,
        preferences=str(user_context.preferences) if user_context.preferences else "无特殊偏好",
    )
    # 注入子Agent委派上下文协议
    if delegation_prompt:
        system_prompt += delegation_prompt

    # ===== 6.5 手动加载 Skill 内容注入提示词 =====
    # 框架内置 skills 加载器无法解析含中文/空格的路径，改为手动加载
    skills_prompt = _load_skills_prompt(SKILLS_DIR)
    if skills_prompt:
        system_prompt += skills_prompt
        agent_logger.info(f"Skills loaded into prompt from {SKILLS_DIR}")

    # ===== 7. 创建 Agent =====
    # ❌ 不传 skills 参数（框架内置 SkillsMiddleware 无法处理含中文路径）
    # ✅ Skills 通过 _load_skills_prompt 注入 system_prompt + SkillsSyncMiddleware 同步到沙箱
    agent = create_deep_agent(
        model=llm,
        tools=all_tools,
        system_prompt=system_prompt,
        middleware=middlewares,
        subagents=subagents if subagents else None,
        skills=None,
        memory=[str(MEMORY_DIR / "AGENTS.md")],
        backend=backend_factory,
        interrupt_on=INTERRUPT_ON_TOOLS,
        checkpointer=checkpointer,
        store=store,
        name="procurement-main-agent",
    )

    agent_logger.info(
        f"Main agent created: {len(all_tools)} tools, "
        f"{len(subagents)} subagents, {len(middlewares)} middlewares"
    )
    return agent
