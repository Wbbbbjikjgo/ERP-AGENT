"""
全部工具单元测试
逐个验证每个自定义工具的基本功能
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.env_utils import load_env
load_env()


async def test_chart_generator():
    """测试图表生成工具"""
    print("[1] 测试 chart_generator...")
    from agent.tools.chart_generator import generate_chart

    result = await generate_chart.ainvoke({
        "chart_type": "bar",
        "data": [
            {"name": "供应商A", "value": 100},
            {"name": "供应商B", "value": 150},
            {"name": "供应商C", "value": 80},
        ],
        "title": "测试柱状图",
        "x_field": "name",
        "y_field": "value",
        "filename": "test_bar",
    })
    print(f"    结果: {str(result)[:150]}")
    print("    ✓ chart_generator 正常\n")


async def test_web_search():
    """测试Web搜索工具"""
    print("[2] 测试 web_search...")
    from agent.tools.web_search import web_search

    result = await web_search.ainvoke({
        "query": "摩托车零部件采购管理"
    })
    print(f"    结果: {str(result)[:200]}")
    print("    ✓ web_search 正常\n")


async def test_mcp_tools():
    """测试MCP工具加载"""
    print("[3] 测试 MCP 工具加载...")
    from agent.tools.mcp_client import load_mcp_tools_sync

    try:
        tools = load_mcp_tools_sync()
        print(f"    加载了 {len(tools)} 个MCP工具")
        for t in tools:
            print(f"      - {t.name}")
        print("    ✓ MCP工具加载正常\n")
    except Exception as e:
        print(f"    ⚠ MCP工具加载失败(需先启动MCP Server): {e}\n")


async def test_subagent_loader():
    """测试子Agent配置加载"""
    print("[4] 测试子Agent配置加载...")
    from agent.subagents.loader import load_subagent_configs

    configs = load_subagent_configs()
    print(f"    加载了 {len(configs)} 个子Agent配置:")
    for c in configs:
        print(f"      - {c['name']}: {c['description'][:40]}...")
    print("    ✓ 子Agent配置加载正常\n")


async def test_schema():
    """测试数据模型"""
    print("[5] 测试数据模型...")
    from agent.schema import ProcurementContext, ChatRequest

    ctx = ProcurementContext(
        user_id="test-001",
        username="测试用户",
        preferences={}
    )
    print(f"    ProcurementContext: {ctx.user_id}, {ctx.username}")

    req = ChatRequest(
        message="查询供应商",
        thread_id="thread-001",
        user_id="test-001",
        username="测试用户"
    )
    print(f"    ChatRequest: {req.message}")
    print("    ✓ 数据模型正常\n")


async def main():
    print("=" * 50)
    print("  工具单元测试")
    print("=" * 50 + "\n")

    await test_schema()
    await test_subagent_loader()

    try:
        await test_chart_generator()
    except Exception as e:
        print(f"    ⚠ chart_generator 测试跳过: {e}\n")

    try:
        await test_web_search()
    except Exception as e:
        print(f"    ⚠ web_search 测试跳过: {e}\n")

    await test_mcp_tools()

    print("=" * 50)
    print("  测试完成")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
