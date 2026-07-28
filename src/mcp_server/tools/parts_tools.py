"""
产品/零部件管理 MCP 工具
part_query / part_search / part_by_supplier / part_page
"""
import json
from fastmcp import FastMCP
from ..http_base import erp_client


def register_parts_tools(mcp: FastMCP):
    """注册零部件管理工具到 MCP Server"""

    @mcp.tool()
    async def part_query(id: int) -> str:
        """获取单个零部件的详细信息。

        Args:
            id: 零部件ID

        Returns:
            零部件详细信息JSON，包含 partCode, name, model, specification, unit, purchasePrice, suggestedRetailPrice, stockWarningValue, supplierId, category, description
        """
        result = await erp_client.get(f"/api/parts/get/{id}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def part_search(name: str) -> str:
        """根据名称关键字搜索零部件。

        Args:
            name: 零件名称关键字，例如"火花塞"、"刹车片"、"滤芯"

        Returns:
            匹配的零部件列表JSON
        """
        result = await erp_client.get("/api/parts/search", params={"name": name})
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def part_by_supplier(supplier_id: int) -> str:
        """获取指定供应商的所有产品列表。

        Args:
            supplier_id: 供应商ID

        Returns:
            该供应商提供的零部件列表JSON
        """
        result = await erp_client.get(f"/api/parts/supplier/{supplier_id}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def part_page(
        current: int = 1,
        size: int = 10,
        name: str = None,
        category: str = None,
        supplier_id: int = None,
    ) -> str:
        """分页查询零部件列表。

        Args:
            current: 当前页码，默认1
            size: 每页大小，默认10
            name: 零件名称（可选，模糊匹配）
            category: 分类（可选），例如"发动机系统"、"制动系统"、"电气系统"
            supplier_id: 供应商ID（可选）

        Returns:
            分页零部件数据JSON，包含 records, total, current, size, pages
        """
        params = {
            "current": current,
            "size": size,
            "name": name,
            "category": category,
            "supplierId": supplier_id,
        }
        result = await erp_client.get("/api/parts/page", params=params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def part_create(
        part_code: str,
        name: str,
        purchase_price: float,
        model: str = None,
        specification: str = None,
        unit: str = None,
        suggested_retail_price: float = None,
        stock_warning_value: int = None,
        supplier_id: int = None,
        category: str = None,
        description: str = None,
    ) -> str:
        """创建新零部件。

        Args:
            part_code: 零件编码（必填）
            name: 零件名称（必填）
            purchase_price: 采购单价（必填，>=0）
            model: 型号
            specification: 规格
            unit: 单位（个/套/件）
            suggested_retail_price: 建议零售价
            stock_warning_value: 库存预警值
            supplier_id: 供应商ID
            category: 分类
            description: 描述

        Returns:
            创建结果JSON
        """
        data = {
            "partCode": part_code,
            "name": name,
            "purchasePrice": purchase_price,
            "model": model,
            "specification": specification,
            "unit": unit,
            "suggestedRetailPrice": suggested_retail_price,
            "stockWarningValue": stock_warning_value,
            "supplierId": supplier_id,
            "category": category,
            "description": description,
        }
        data = {k: v for k, v in data.items() if v is not None}
        result = await erp_client.post("/api/parts/create", json_data=data)
        return json.dumps(result, ensure_ascii=False, indent=2)
