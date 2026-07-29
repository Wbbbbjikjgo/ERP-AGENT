"""
MCP 工具分类 Bean
将 MCP 工具按用途分组：analyst_tools / order_tools。
"""
from typing import List
from langchain_core.tools import BaseTool


# 分析子Agent使用的工具名关键字
ANALYST_TOOL_PATTERNS = [
    "supplier_query",
    "supplier_page",
    "supplier_get",
    "part_search",
    "part_page",
    "part_query",
    "part_by_supplier",
    "inventory_warning",
    "inventory_page",
    "inventory_check",
    "inventory_get",
    "order_search_details",
    "order_statistics",
    "order_page",
    "order_get",
    "generate_chart",
    "web_search",
]

# 订单子Agent使用的工具名关键字
ORDER_TOOL_PATTERNS = [
    "order_create",
    "order_update",
    "order_get",
    "order_page",
    "order_update_status",
    "request_order_info",
    "part_query",
    "part_search",
    "supplier_query",
    "supplier_get",
]


def classify_tools(all_tools: List[BaseTool]) -> dict:
    """将工具按用途分类"""
    tool_map = {t.name: t for t in all_tools}

    analyst_tools = []
    order_tools = []

    for pattern in ANALYST_TOOL_PATTERNS:
        for name, tool in tool_map.items():
            if pattern in name and tool not in analyst_tools:
                analyst_tools.append(tool)

    for pattern in ORDER_TOOL_PATTERNS:
        for name, tool in tool_map.items():
            if pattern in name and tool not in order_tools:
                order_tools.append(tool)

    return {
        "analyst_tools": analyst_tools,
        "order_tools": order_tools,
        "all_tools": all_tools,
    }
