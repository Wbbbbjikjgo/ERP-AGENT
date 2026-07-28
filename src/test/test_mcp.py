"""
MCP Server 连接测试
验证 MCP Server 是否正常运行，所有工具是否可调用
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.env_utils import load_env
load_env()


async def test_mcp_connection():
    """测试 MCP Server 连接和工具调用"""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    mcp_url = os.getenv("MCP_SERVER_URL", "http://localhost:9000")
    print(f"[1] 连接 MCP Server: {mcp_url}/sse")

    client = MultiServerMCPClient({
        "erp": {
            "url": f"{mcp_url}/sse",
            "transport": "sse",
        }
    })

    try:
        tools = await client.get_tools()
        print(f"[2] 获取到 {len(tools)} 个工具:")
        for t in tools:
            print(f"    - {t.name}: {t.description[:50]}...")

        # 测试 supplier_query
        print("\n[3] 测试 supplier_query...")
        supplier_tool = next((t for t in tools if "supplier" in t.name), None)
        if supplier_tool:
            result = await supplier_tool.ainvoke({"name": ""})
            print(f"    结果: {str(result)[:200]}")
        else:
            print("    ⚠ 未找到 supplier 工具")

        # 测试 inventory_warning
        print("\n[4] 测试 inventory_warning...")
        inv_tool = next((t for t in tools if "inventory" in t.name), None)
        if inv_tool:
            result = await inv_tool.ainvoke({})
            print(f"    结果: {str(result)[:200]}")
        else:
            print("    ⚠ 未找到 inventory 工具")

        # 测试 part_page
        print("\n[5] 测试 part_page...")
        part_tool = next((t for t in tools if "part" in t.name), None)
        if part_tool:
            result = await part_tool.ainvoke({"current": 1, "size": 5})
            print(f"    结果: {str(result)[:200]}")
        else:
            print("    ⚠ 未找到 part 工具")

        print("\n✓ MCP 测试完成")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_mcp_connection())
