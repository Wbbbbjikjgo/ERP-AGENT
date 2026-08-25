"""
子Agent配置加载器
核心职责：
1. 读取 configs/*.yaml 并校验必填字段
2. 将 tools 字符串通过子串匹配映射为实际工具对象
3. 解析 interrupt_on 配置
4. 将 context_protocol 注入到主Agent系统提示词
"""
import yaml  # 导入 YAML 解析库，用于读取 .yaml 配置文件
from pathlib import Path  # 导入路径库，用于处理文件路径
from deepagents import SubAgent  # 导入子Agent类型（用于类型注解）
from langchain_core.tools import BaseTool  # 导入工具基类，用于类型注解
from ..log_utils import agent_logger  # 导入日志工具

# 配置文件目录：当前文件所在目录下的 configs 文件夹
CONFIGS_DIR = Path(__file__).parent / "configs"
# 子Agent配置的必填字段列表
# 每个子Agent配置文件必须包含这些字段
REQUIRED_FIELDS = ["name", "description", "system_prompt", "tools"]


def _validate_subagent_config(config: dict) -> bool:
    """校验子Agent配置必填字段
    
    检查配置字典是否包含所有必填字段，且字段值不为空
    
    Args:
        config: 从 YAML 文件加载的配置字典
    
    Returns:
        True 表示校验通过，False 表示校验失败
    """
    # 使用 all() 检查每个必填字段是否都存在且非空
    # config[field] 在字段存在且值非空时返回 True
    return all(field in config and config[field] for field in REQUIRED_FIELDS)


def _get_output_format(config: dict) -> dict | None:
    """提取子Agent的输出契约定义（支持顶层 output_format 或 context_protocol.output_format）"""
    output_format = config.get("output_format")
    if isinstance(output_format, dict):
        return output_format
    protocol = config.get("context_protocol")
    if isinstance(protocol, dict):
        nested = protocol.get("output_format")
        if isinstance(nested, dict):
            return nested
    return None


def _validate_output_format(config: dict) -> bool:
    """校验子Agent的 output_format 契约结构（声明式输出契约的强校验）

    校验规则：
    - output_format 必须为 dict
    - 若含 sections 字段，必须是字符串列表

    Args:
        config: 子Agent配置字典

    Returns:
        True 表示结构合法（或未声明 output_format，向后兼容），False 表示非法
    """
    output_format = _get_output_format(config)
    if output_format is None:
        return True  # 未声明输出契约，不强制
    sections = output_format.get("sections")
    if sections is not None and (
        not isinstance(sections, list)
        or not all(isinstance(s, str) for s in sections)
    ):
        agent_logger.error(
            f"Invalid output_format.sections in {config.get('name')}: must be a list of strings"
        )
        return False
    return True


def build_output_contract_prompt(config: dict) -> str:
    """根据 output_format 生成输出契约提示词（注入子Agent system_prompt）。

    使 YAML 中声明的输出结构成为子Agent必须遵守的显式契约，
    并由主Agent的 RubricMiddleware 依据评审标准对子Agent输出做校验。
    """
    output_format = _get_output_format(config)
    if output_format is None:
        return ""

    fmt_type = output_format.get("type", "structured_report")
    sections = output_format.get("sections", [])
    fmt = output_format.get("format", "markdown")

    if not sections:
        return ""

    lines = [
        "\n\n## 输出契约（必须严格遵守）",
        f"你的最终返回结果必须符合以下结构化契约（类型：{fmt_type}，格式：{fmt}）：",
    ]
    for i, section in enumerate(sections, 1):
        lines.append(f"{i}. **{section}**")

    lines.append(
        "主Agent 将依据此契约对你的输出进行校验；缺失任一 section 将被视为不合格并触发返工。"
    )
    return "\n".join(lines)


def _parse_interrupt_on(config: dict) -> dict | None:
    """解析 YAML 中的 interrupt_on 配置为框架格式
    
    interrupt_on 用于配置人工审批流程：
    当子Agent调用某些工具时，需要等待人工审批才能继续
    
    YAML 格式示例：
    interrupt_on:
      delete_record:
        allowed_decisions: ["approve", "reject"]
        description: "删除记录需要管理员审批"
    
    Args:
        config: 子Agent配置字典
    
    Returns:
        解析后的 interrupt_on 字典，如果没有配置则返回 None
    """
    # 从配置中获取 interrupt_on 字段（可能不存在）
    raw = config.get("interrupt_on")
    
    # 如果没有配置，直接返回 None
    if not raw:
        return None
    
    # 解析后的结果字典
    parsed = {}
    
    # 遍历每个工具名称及其配置
    for tool_name, tool_config in raw.items():
        # 检查工具配置是否为字典格式
        if isinstance(tool_config, dict):
            # 构建框架需要的格式
            parsed[tool_name] = {
                # 允许的决策列表（默认 approve 和 reject）
                "allowed_decisions": tool_config.get("allowed_decisions", ["approve", "reject"]),
            }
            # 如果配置中有描述，也一并添加
            if "description" in tool_config:
                parsed[tool_name]["description"] = tool_config["description"]
    
    return parsed


def load_subagent_configs() -> list[dict]:
    """读取 configs/*.yaml，校验必填字段
    
    扫描配置目录下的所有 YAML 文件，加载并校验配置
    
    Returns:
        通过校验的配置列表（未通过校验的会被跳过并记录日志）
    """
    configs = []  # 存储通过校验的配置
    
    # 遍历 configs 目录下所有 .yaml 文件（按文件名排序）
    for yaml_file in sorted(CONFIGS_DIR.glob("*.yaml")):
        try:
            # 打开并读取 YAML 文件
            with open(yaml_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)  # 安全加载 YAML 内容
        except Exception as e:
            # 读取或解析失败，记录错误日志并跳过该文件
            agent_logger.error(f"Failed to load {yaml_file}: {e}")
            continue
        
        # 校验配置是否包含所有必填字段
        if config and _validate_subagent_config(config):
            # 校验通过，添加到结果列表
            configs.append(config)
            agent_logger.info(f"Loaded subagent config: {config['name']}")
        else:
            # 校验失败，记录警告日志
            agent_logger.warning(f"Invalid config in {yaml_file}: missing required fields")
    
    # 返回所有通过校验的配置
    return configs


def resolve_subagent_tools(configs: list[dict], all_tools: list[BaseTool]) -> list:
    """将 tools 字符串通过子串匹配映射为实际工具对象
    
    匹配规则：pattern in tool.name（子串包含匹配）
    例如："supplier" 会匹配 "supplier_query", "supplier_page", "supplier_get"
    
    这种设计允许用户在配置文件中只写 "supplier"，就能自动匹配所有相关工具
    
    Args:
        configs: 子Agent配置列表（来自 load_subagent_configs）
        all_tools: 所有可用工具的完整列表
    
    Returns:
        包含工具对象解析结果的子Agent规格列表（可直接用于创建 SubAgent）
    """
    subagents = []  # 存储解析后的子Agent规格
    
    # 遍历每个子Agent配置
    for config in configs:
        # 获取配置中的工具模式列表（字符串列表）
        tool_patterns = config.get("tools", [])
        
        # 存储匹配到的实际工具对象
        matched_tools = []
        
        # 遍历每个工具模式字符串
        for pattern in tool_patterns:
            # 遍历所有可用工具
            for tool in all_tools:
                # 检查模式字符串是否包含在工具名称中（子串匹配）
                # 且该工具尚未被添加（避免重复）
                if pattern in tool.name and tool not in matched_tools:
                    matched_tools.append(tool)
        
        # 解析 interrupt_on 配置
        interrupt_on = _parse_interrupt_on(config)

        # 校验 output_format 契约结构（非法则记录错误，仍继续创建但契约不注入）
        output_contract = ""
        if _validate_output_format(config):
            output_contract = build_output_contract_prompt(config)

        # 构建子Agent规格字典
        subagent_spec = {
            "name": config["name"],
            "description": config["description"],
            "system_prompt": config["system_prompt"] + output_contract,
            "tools": matched_tools,
        }
        
        # 如果有 interrupt_on 配置，添加到规格中
        if interrupt_on:
            subagent_spec["interrupt_on"] = interrupt_on
        
        # 添加到结果列表
        subagents.append(subagent_spec)
    
    return subagents


def get_delegation_context_prompt(configs: list[dict]) -> str:
    """生成主Agent的委派上下文提示词片段
    
    告诉主Agent在委派任务给子Agent时，应该传递哪些上下文信息。
    这个提示词会被注入到主Agent的系统提示词中。
    
    Args:
        configs: 子Agent配置列表
    
    Returns:
        格式化的上下文协议提示词字符串
    """
    sections = []  # 存储每个子Agent的协议说明
    
    # 遍历每个子Agent配置
    for config in configs:
        # 获取 context_protocol 配置
        protocol = config.get("context_protocol")
        
        # 如果没有配置上下文协议，跳过该子Agent
        if not protocol:
            continue
        
        # 获取输入上下文字段列表
        input_ctx = protocol.get("input_context", [])
        
        # 构建该子Agent的协议说明行
        lines = [f"\n### 委派给 {config['name']} 时的上下文传递要求"]
        
        # 遍历每个上下文字段定义
        for field_def in input_ctx:
            field = field_def.get("field", "")  # 字段名
            desc = field_def.get("description", "")  # 字段描述
            required = field_def.get("required", False)  # 是否必填
            
            # 根据是否必填添加标记
            marker = "**[必填]**" if required else "[可选]"
            
            # 添加字段说明行
            lines.append(f"- {marker} `{field}`: {desc}")
        
        # 将该子Agent的协议说明添加到节列表
        sections.append("\n".join(lines))
    
    # 如果有协议说明，组装成完整的提示词片段
    if sections:
        return "\n## 子Agent委派上下文协议\n" + "\n".join(sections)
    else:
        # 没有配置任何上下文协议，返回空字符串
        return ""