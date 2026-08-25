"""
Harness 编排模块（真 Harness 架构核心）

职责：
1. HarnessPhaseState — 扩展 LangGraph 状态（phase / plan / review_result）
2. load_harness_config — 加载声明式 DSL 配置（harness_config.yaml）
3. build_rubric / detect_task_type — 按任务类型生成评审标准
4. HarnessPhaseMiddleware — 阶段状态机 + rubric 注入

设计说明：
- 阶段（phase）不再是 chat.py 里的正则猜测，而是 graph state 中的结构化字段，
  由中间件在钩子中写入，可被 checkpoint 持久化、可被 values 流读取。
- 评审（review）交给框架原生 RubricMiddleware：注入 rubric 后，
  其 grader 子Agent 会结构化产出 satisfied / needs_revision / failed 判定，
  needs_revision 时自动打回模型重做，形成真正的 Review 回路。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from typing_extensions import NotRequired, TypedDict

from langchain.agents.middleware import AgentMiddleware, Runtime
from langchain.agents.middleware.types import AgentState

from .schema import Phase
from .log_utils import agent_logger

# DSL 配置文件路径
HARNESS_CONFIG_PATH = Path(__file__).parent / "harness_config.yaml"


class HarnessPhaseState(AgentState):
    """Harness 扩展状态：在 DeepAgentState 基础上增加阶段/计划/评审字段。

    通过 HarnessPhaseMiddleware.state_schema 声明，由框架自动合并进 graph state，
    因此这些字段会出现在 checkpoint 和 values 流中（可观测、可恢复）。
    """

    phase: NotRequired[str]
    """当前阶段：planning / executing / reviewing / result（见 schema.Phase）"""

    plan: NotRequired[dict]
    """结构化任务规划（schema.Plan 序列化后的 dict）"""

    review_result: NotRequired[dict]
    """评审结果（schema.ReviewResult 序列化后的 dict）"""


# 配置缺失时的兜底（避免文件缺失导致整个 Agent 启动失败）
_DEFAULT_CONFIG: dict[str, Any] = {
    "review": {"max_iterations": 3, "model": None},
    "task_types": {},
    "rubrics": {"default": "1. 完整回答用户问题，未遗漏关键信息\n2. 数据来自真实工具调用\n3. 输出格式规范"},
}


def load_harness_config(config_path: Path | None = None) -> dict[str, Any]:
    """加载 Harness DSL 配置。

    Args:
        config_path: 配置文件路径，默认使用模块目录下的 harness_config.yaml。

    Returns:
        配置字典。文件缺失或解析失败时回退到 _DEFAULT_CONFIG（保证降级可用）。
    """
    path = config_path or HARNESS_CONFIG_PATH
    if not path.exists():
        agent_logger.warning(f"Harness config not found at {path}, using defaults")
        return _DEFAULT_CONFIG

    try:
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        return config if isinstance(config, dict) else _DEFAULT_CONFIG
    except Exception as e:
        agent_logger.error(f"Failed to load harness config: {e}, using defaults")
        return _DEFAULT_CONFIG


def detect_task_type(messages: list[Any], config: dict[str, Any]) -> str:
    """根据用户消息识别任务类型，用于选择对应的评审标准。

    规则：取最近一条 HumanMessage 的文本，按 task_types 的关键词命中判定。
    多个类型命中时取关键词命中数量最多者；无命中返回 "default"。
    """
    task_types = config.get("task_types", {})
    if not task_types:
        return "default"

    # 收集用户消息文本（取最近的人类消息）
    user_text = ""
    for msg in reversed(messages or []):
        if getattr(msg, "type", "") == "human":
            user_text = str(getattr(msg, "content", "") or "")
            break

    if not user_text:
        return "default"

    best_type, best_score = "default", 0
    for task_type, spec in task_types.items():
        keywords = spec.get("keywords", []) if isinstance(spec, dict) else []
        score = sum(1 for kw in keywords if kw in user_text)
        if score > best_score:
            best_type, best_score = task_type, score

    return best_type


def build_rubric(task_type: str, config: dict[str, Any]) -> str:
    """按任务类型生成评审标准（rubric）字符串。

    RubricMiddleware 收到该字符串后，会由 grader 子Agent 逐条对照
    执行记录（transcript）打分，驱动"是否重做"的判定。
    """
    rubrics = config.get("rubrics", {})
    rubric = rubrics.get(task_type) or rubrics.get("default", "")
    return rubric.strip()


class HarnessPhaseMiddleware(AgentMiddleware):
    """Harness 阶段状态机中间件。

    职责：
    - before_agent: 识别任务类型 → 注入 rubric（激活 RubricMiddleware）→ 置 phase=planning
    - after_agent:  置 phase=result（终态）

    阶段字段写入 state，供 chat.py 从 values 流读取并向前端发射结构化 SSE 事件，
    替代原先对 LLM 输出文本的正则猜测。
    """

    state_schema = HarnessPhaseState

    def __init__(self, config_path: Path | None = None):
        self._config = load_harness_config(config_path)
        self.tools = []

    @property
    def name(self) -> str:
        return "HarnessPhaseMiddleware"

    def before_agent(self, state: Any, runtime: Runtime) -> dict[str, Any] | None:
        """执行前：注入 rubric + 置初始阶段为 planning。"""
        updates: dict[str, Any] = {"phase": Phase.planning.value}

        # 若调用方已显式传入 rubric，则不覆盖（保留外部评审标准）
        if state.get("rubric"):
            agent_logger.debug("Rubric already provided, skip auto-injection")
            return updates

        task_type = detect_task_type(state.get("messages", []), self._config)
        rubric = build_rubric(task_type, self._config)
        if rubric:
            updates["rubric"] = rubric
            agent_logger.info(f"Harness rubric injected (task_type={task_type})")

        return updates

    def after_agent(self, state: Any, runtime: Runtime) -> dict[str, Any] | None:
        """执行后：置终态阶段为 result。"""
        return {"phase": Phase.result.value}
