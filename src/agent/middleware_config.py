"""
子Agent中间件工厂（Harness 架构 — 完整中间件栈）

为 analyst / order 子Agent 提供专用中间件配置。
每个子Agent都有完整的中间件栈，而非仅一个 demo 中间件。

中间件栈（子Agent版）：
1. SummarizationToolMiddleware  — 长对话自动压缩（大量数据分析时必备）
2. ContextInjectionMiddleware   — 子Agent专用上下文注入
3. SkillsSyncMiddleware         — 技能文件同步（子Agent执行代码时需要）
4. SandboxCircuitBreakerMiddleware — 沙箱熔断器（防止子Agent陷入无限重试）

与主Agent中间件栈的关系：
- 主Agent：7个自定义中间件 + 框架内置
- 子Agent：4个精选中间件 + 框架内置（轻量化，聚焦子Agent任务）
"""
from pathlib import Path
from deepagents.middleware import SummarizationToolMiddleware

from .middlewares.context_injection import ContextInjectionMiddleware
from .middlewares.skills_sync import SkillsSyncMiddleware
from .middlewares.sandbox_breaker import SandboxCircuitBreakerMiddleware
from .middlewares.tools_summarization import ToolsSummarizationMiddleware
from .schema import ProcurementContext


# 技能目录
SKILLS_DIR = Path(__file__).parent.parent / "skills"


def get_analyst_middleware(user_context: ProcurementContext | None = None) -> list:
    """
    获取采购分析子Agent的中间件列表

    分析子Agent的特点：
    - 需要处理大量数据结果 → SummarizationMiddleware
    - 需要执行代码生成图表 → SkillsSyncMiddleware
    - 需要感知用户偏好 → ContextInjectionMiddleware
    - 沙箱工具调用频繁 → CircuitBreakerMiddleware
    """
    context = user_context or ProcurementContext(username="采购分析师")

    return [
        # 1. 对话压缩（分析任务数据量大，容易上下文溢出）
        SummarizationToolMiddleware(),

        # 2. 上下文注入（注入用户偏好，如图表类型）
        ContextInjectionMiddleware(user_context=context),

        # 3. 技能同步（分析子Agent可能需要调用脚本）
        SkillsSyncMiddleware(skills_dir=SKILLS_DIR),

        # 4. 摘要监控（采购领域定制）
        ToolsSummarizationMiddleware(),

        # 5. 沙箱熔断器（连续失败时降级）
        SandboxCircuitBreakerMiddleware(failure_threshold=3, recovery_timeout=60),
    ]


def get_order_middleware(user_context: ProcurementContext | None = None) -> list:
    """
    获取采购订单子Agent的中间件列表

    订单子Agent的特点：
    - 订单操作有中断审批流程 → 需要 SummarizationMiddleware 保持上下文
    - 需要用户身份确认 → ContextInjectionMiddleware
    - 沙箱操作较少但关键 → CircuitBreakerMiddleware
    """
    context = user_context or ProcurementContext(username="采购订单专员")

    return [
        # 1. 对话压缩（订单审批多轮对话）
        SummarizationToolMiddleware(),

        # 2. 上下文注入（注入用户身份，订单需要记录操作人）
        ContextInjectionMiddleware(user_context=context),

        # 3. 技能同步
        SkillsSyncMiddleware(skills_dir=SKILLS_DIR),

        # 4. 摘要监控
        ToolsSummarizationMiddleware(),

        # 5. 沙箱熔断器
        SandboxCircuitBreakerMiddleware(failure_threshold=3, recovery_timeout=60),
    ]


def get_all_subagent_middlewares(user_context: ProcurementContext | None = None) -> dict:
    """
    获取所有子Agent的中间件配置（供 main_agent 统一加载）

    Returns:
        {subagent_name: [middleware_list]}
    """
    return {
        "procurement-analyst": get_analyst_middleware(user_context),
        "procurement-order": get_order_middleware(user_context),
    }
