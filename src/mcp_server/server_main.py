"""
MCP Server 入口
FastMCP 实例创建，注册所有 tools，SSE 传输协议
"""
import sys
import os

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastmcp import FastMCP
from src.mcp_server.server_config import MCP_HOST, MCP_PORT
from src.mcp_server.tools.suppliers_tools import register_supplier_tools
from src.mcp_server.tools.parts_tools import register_parts_tools
from src.mcp_server.tools.order_tools import register_order_tools
from src.mcp_server.tools.inventory_tools import register_inventory_tools

# 创建 MCP Server 实例
mcp = FastMCP(
    name="ERP-Procurement-MCP",
    instructions="摩托车零部件采购管理系统 MCP 网关，提供供应商、零部件、订单、库存查询和管理能力。",
)

# 注册所有工具
register_supplier_tools(mcp)
register_parts_tools(mcp)
register_order_tools(mcp)
register_inventory_tools(mcp)


if __name__ == "__main__":
    print(f"🚀 Starting MCP Server on {MCP_HOST}:{MCP_PORT} (SSE transport)")
    mcp.run(transport="sse", host=MCP_HOST, port=MCP_PORT)
