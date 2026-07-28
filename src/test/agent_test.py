"""
端到端 Agent 测试
模拟完整对话流程，验证 Agent 核心功能
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.env_utils import load_env
load_env()


async def test_agent_creation():
    """测试 Agent 创建"""
    print("[1] 测试 Agent 创建...")
    from agent.schema import ProcurementContext
    from agent.main_agent import create_main_agent

    ctx = ProcurementContext(
        user_id="test-e2e",
        username="端到端测试",
        preferences={}
    )

    agent = create_main_agent(user_context=ctx)
    print(f"    Agent 类型: {type(agent).__name__}")
    print("    ✓ Agent 创建成功\n")
    return agent


async def test_simple_query(agent):
    """测试简单查询"""
    print("[2] 测试简单查询: '你好，请介绍一下你的功能'")
    config = {"configurable": {"thread_id": "test-e2e-001"}}

    try:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "你好，请介绍一下你的功能"}]},
            config=config,
        )
        messages = result.get("messages", [])
        if messages:
            last = messages[-1]
            content = last.content if hasattr(last, "content") else str(last)
            print(f"    回复: {content[:200]}...")
        print("    ✓ 简单查询正常\n")
    except Exception as e:
        print(f"    ⚠ 查询失败: {e}\n")


async def test_supplier_query(agent):
    """测试供应商查询"""
    print("[3] 测试供应商查询: '查询所有供应商'")
    config = {"configurable": {"thread_id": "test-e2e-002"}}

    try:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "查询所有供应商信息"}]},
            config=config,
        )
        messages = result.get("messages", [])
        if messages:
            last = messages[-1]
            content = last.content if hasattr(last, "content") else str(last)
            print(f"    回复: {content[:300]}...")
        print("    ✓ 供应商查询正常\n")
    except Exception as e:
        print(f"    ⚠ 查询失败: {e}\n")


async def test_inventory_warning(agent):
    """测试库存预警"""
    print("[4] 测试库存预警: '查看库存预警'")
    config = {"configurable": {"thread_id": "test-e2e-003"}}

    try:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "查看当前库存预警信息"}]},
            config=config,
        )
        messages = result.get("messages", [])
        if messages:
            last = messages[-1]
            content = last.content if hasattr(last, "content") else str(last)
            print(f"    回复: {content[:300]}...")
        print("    ✓ 库存预警正常\n")
    except Exception as e:
        print(f"    ⚠ 查询失败: {e}\n")


async def main():
    print("=" * 60)
    print("  端到端 Agent 测试")
    print("  前置条件: MCP Server 已启动 (port 9000)")
    print("            MongoDB 已启动 (port 27017)")
    print("=" * 60 + "\n")

    try:
        agent = await test_agent_creation()
    except Exception as e:
        print(f"✗ Agent 创建失败: {e}")
        print("  请检查: 1) MCP Server是否启动  2) 依赖是否安装")
        return

    await test_simple_query(agent)
    await test_supplier_query(agent)
    await test_inventory_warning(agent)

    print("=" * 60)
    print("  端到端测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
