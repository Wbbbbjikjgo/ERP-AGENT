"""
库存管理 MCP 工具
inventory_warning / inventory_page / inventory_check / inventory_inbound / inventory_outbound
"""
import json
from fastmcp import FastMCP
from ..http_base import erp_client


def register_inventory_tools(mcp: FastMCP):
    """注册库存管理工具到 MCP Server"""

    @mcp.tool()
    async def inventory_warning() -> str:
        """获取库存预警列表，返回当前库存量低于安全库存的所有零部件。

        Returns:
            库存预警列表JSON，每条包含库存信息和零部件详情（名称、编码、分类等）
        """
        result = await erp_client.get("/api/inventory/warning")
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def inventory_page(
        current: int = 1,
        size: int = 10,
        part_name: str = None,
        warehouse_location: str = None,
    ) -> str:
        """分页查询库存列表。

        Args:
            current: 当前页码，默认1
            size: 每页大小，默认10
            part_name: 零件名称（可选，模糊匹配）
            warehouse_location: 仓库位置（可选）

        Returns:
            分页库存数据JSON，包含 currentQuantity, safetyStock, warehouseLocation, partDetail
        """
        params = {
            "current": current,
            "size": size,
            "partName": part_name,
            "warehouseLocation": warehouse_location,
        }
        result = await erp_client.get("/api/inventory/page", params=params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def inventory_check() -> str:
        """执行库存盘点，返回库存总览统计。

        Returns:
            库存盘点统计JSON，包含总SKU数、预警数量、总库存价值等
        """
        result = await erp_client.get("/api/inventory/check")
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def inventory_inbound(
        part_id: int,
        quantity: int,
        warehouse_location: str = None,
    ) -> str:
        """执行入库操作。

        Args:
            part_id: 零件ID（必填）.
            quantity: 入库数量（必填，>0）
            warehouse_location: 仓库位置（可选）

        Returns:
            操作结果JSON
        """
        params = {
            "partId": part_id,
            "quantity": quantity,
            "warehouseLocation": warehouse_location,
        }
        result = await erp_client.post("/api/inventory/inbound", params=params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def inventory_outbound(part_id: int, quantity: int) -> str:
        """执行出库操作。

        Args:
            part_id: 零件ID（必填）
            quantity: 出库数量（必填，>0）

        Returns:
            操作结果JSON
        """
        params = {
            "partId": part_id,
            "quantity": quantity,
        }
        result = await erp_client.post("/api/inventory/outbound", params=params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def inventory_get(id: int) -> str:
        """获取单条库存记录详情。

        Args:
            id: 库存记录ID

        Returns:
            库存详情JSON
        """
        result = await erp_client.get(f"/api/inventory/get/{id}")
        return json.dumps(result, ensure_ascii=False, indent=2)
