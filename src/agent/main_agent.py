"""
主入口：create_main_agent() + precompute_agent_context()
DeepAgent 核心组装 — 严格遵循 Harness Engineering 架构
"""
import os
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

    mcp_tools = load_mcp_tools_sync()
    custom_tools = [generate_chart, web_search, web_fetch, install_skill, request_order_info]
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
        SkillsSyncMiddleware(skills_dir=SKILLS_DIR),                  # 3. 技能同步
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

    # ===== 7. 创建 Agent =====
    agent = create_deep_agent(
        model=llm,
        tools=all_tools,
        system_prompt=system_prompt,
        middleware=middlewares,
        subagents=subagents if subagents else None,
        skills=[str(SKILLS_DIR)],
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
