"""
子Agent配置加载器
YAML 加载 + 工具名解析 + interrupt_on 解析 + 上下文协议注入 + 必填字段校验

核心职责：
1. 读取 configs/*.yaml 并校验必填字段
2. 将 tools 字符串模式匹配为实际工具对象
3. 解析 interrupt_on 配置 → InterruptOnConfig 格式
4. 将 context_protocol 注入到 system_prompt（让子Agent知道接收什么上下文）
5. 构造 SubAgent TypedDict 实例
"""
import os
from pathlib import Path
from typing import Any, List

import yaml
from deepagents import SubAgent
from langchain_core.tools import BaseTool

from ..log_utils import agent_logger

CONFIGS_DIR = Path(__file__).parent / "configs"

REQUIRED_FIELDS = ["name", "description", "system_prompt", "tools"]


def _validate_subagent_config(config: dict) -> bool:
    """校验子Agent配置必填字段"""
    for field in REQUIRED_FIELDS:
        if field not in config or not config[field]:
            agent_logger.error(f"SubAgent config missing required field: {field}")
            return False
    return True


def _parse_interrupt_on(config: dict) -> dict[str, Any] | None:
    """
    解析 YAML 中的 interrupt_on 配置为框架 InterruptOnConfig 格式。

    YAML 格式:
        interrupt_on:
          order_create:
            allowed_decisions: [approve, reject, edit]
            description: "审批描述"

    转换为:
        {"order_create": {"allowed_decisions": [...], "description": "..."}}
    """
    raw_interrupt = config.get("interrupt_on")
    if not raw_interrupt or not isinstance(raw_interrupt, dict):
        return None

    parsed = {}
    for tool_name, tool_config in raw_interrupt.items():
        if isinstance(tool_config, bool):
            # 简单模式: interrupt_on: {order_create: true}
            parsed[tool_name] = tool_config
        elif isinstance(tool_config, dict):
            # 完整模式: InterruptOnConfig
            interrupt_config: dict[str, Any] = {
                "allowed_decisions": tool_config.get(
                    "allowed_decisions", ["approve", "reject"]
                ),
            }
            if "description" in tool_config:
                interrupt_config["description"] = tool_config["description"]
            if "args_schema" in tool_config:
                interrupt_config["args_schema"] = tool_config["args_schema"]
            parsed[tool_name] = interrupt_config
        else:
            agent_logger.warning(
                f"Invalid interrupt_on config for '{tool_name}': {type(tool_config)}"
            )

    if parsed:
        agent_logger.info(
            f"SubAgent '{config.get('name')}': interrupt_on configured for {list(parsed.keys())}"
        )
    return parsed


def _build_context_prompt_section(config: dict) -> str:
    """
    从 context_protocol 生成注入到主Agent系统提示词的委派说明。

    这段文本会被附加到主Agent的 system_prompt 中，
    告诉主Agent在委派任务时应该传递哪些上下文信息。
    """
    protocol = config.get("context_protocol")
    if not protocol:
        return ""

    input_ctx = protocol.get("input_context", [])
    output_fmt = protocol.get("output_format", {})

    if not input_ctx:
        return ""

    lines = [f"\n### 委派给 {config['name']} 时的上下文传递要求\n"]
    lines.append("调用 task 工具委派任务时，prompt 中必须包含以下上下文：")

    for field_def in input_ctx:
        field = field_def.get("field", "")
        desc = field_def.get("description", "")
        required = field_def.get("required", False)
        marker = "**[必填]**" if required else "[可选]"
        lines.append(f"- {marker} `{field}`: {desc}")

    if output_fmt:
        lines.append(f"\n子Agent返回格式: {output_fmt.get('type', 'text')}")
        sections = output_fmt.get("sections", [])
        if sections:
            lines.append(f"包含部分: {', '.join(sections)}")

    return "\n".join(lines)


def load_subagent_configs() -> List[dict]:
    """
    读取 configs/*.yaml，校验必填字段，返回原始 dict 列表。
    此时 tools 仍是字符串名称列表。
    """
    configs = []
    if not CONFIGS_DIR.exists():
        agent_logger.warning(f"SubAgent configs directory not found: {CONFIGS_DIR}")
        return configs

    for yaml_file in sorted(CONFIGS_DIR.glob("*.yaml")):
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            if config and _validate_subagent_config(config):
                config["_source_file"] = str(yaml_file)
                configs.append(config)
                agent_logger.info(f"Loaded subagent config: {config['name']} from {yaml_file.name}")
            else:
                agent_logger.warning(f"Invalid subagent config: {yaml_file.name}")
        except Exception as e:
            agent_logger.error(f"Failed to load {yaml_file.name}: {e}")

    return configs


def resolve_subagent_tools(configs: List[dict], all_tools: List[BaseTool]) -> List[SubAgent]:
    """
    将 tools 字符串通过子串匹配映射为实际工具对象，
    解析 interrupt_on，构造 SubAgent TypedDict 实例列表。
    """
    subagents = []

    for config in configs:
        # 子串匹配：pattern in tool.name
        tool_patterns = config.get("tools", [])
        matched_tools = []

        for pattern in tool_patterns:
            for tool in all_tools:
                if pattern in tool.name and tool not in matched_tools:
                    matched_tools.append(tool)

        if not matched_tools:
            agent_logger.warning(
                f"SubAgent '{config['name']}': no tools matched patterns {tool_patterns}"
            )

        # 解析 interrupt_on 配置
        interrupt_on = _parse_interrupt_on(config)

        # 构造 SubAgent TypedDict
        try:
            subagent_spec: dict[str, Any] = {
                "name": config["name"],
                "description": config["description"],
                "system_prompt": config["system_prompt"],
                "tools": matched_tools,
            }

            # 仅在配置了 interrupt_on 时添加
            if interrupt_on:
                subagent_spec["interrupt_on"] = interrupt_on

            subagents.append(subagent_spec)
            agent_logger.info(
                f"SubAgent '{config['name']}' created with {len(matched_tools)} tools: "
                f"{[t.name for t in matched_tools]}"
                + (f", interrupt_on={list(interrupt_on.keys())}" if interrupt_on else "")
            )
        except Exception as e:
            agent_logger.error(f"Failed to create SubAgent '{config['name']}': {e}")

    return subagents


def get_delegation_context_prompt(configs: List[dict]) -> str:
    """
    生成主Agent的委派上下文提示词片段。

    这段文本应该被注入到主Agent的 system_prompt 中，
    让主Agent知道在委派任务时应该传递哪些上下文信息。

    Returns:
        格式化的委派说明文本（Markdown）
    """
    sections = []
    for config in configs:
        section = _build_context_prompt_section(config)
        if section:
            sections.append(section)

    if not sections:
        return ""

    header = "\n## 子Agent委派上下文协议\n"
    header += "委派任务给子Agent时，必须在 task prompt 中传递规定的上下文字段。\n"
    return header + "\n".join(sections)
