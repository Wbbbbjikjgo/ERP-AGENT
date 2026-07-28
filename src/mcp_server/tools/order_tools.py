"""
采购订单管理 MCP 工具
order_create / order_update / order_page / order_get / order_search_details / order_statistics
"""
import json
from typing import Optional
from fastmcp import FastMCP
from ..http_base import erp_client


def register_order_tools(mcp: FastMCP):
    """注册采购订单管理工具到 MCP Server"""

    @mcp.tool()
    async def order_create(order_data: str) -> str:
        """创建采购订单。

        Args:
            order_data: 订单数据JSON字符串，格式：
                {
                    "orderNumber": "PO20260101001",  // 必填，订单编号
                    "totalAmount": 1000.0,           // 总金额
                    "status": 0,                     // 状态：0=待审核,1=已审核,2=已发货,3=已收货,4=已完成
                    "remark": "备注",
                    "orderDetail": [                 // 订单明细列表
                        {
                            "partId": 1,            // 必填，零部件ID
                            "quantity": 100,        // 必填，数量>=1
                            "unitPrice": 25.5,      // 必填，单价
                            "remark": "明细备注"
                        }
                    ]
                }

        Returns:
            创建结果JSON，包含订单ID和完整订单信息
        """
        try:
            data = json.loads(order_data) if isinstance(order_data, str) else order_data
        except json.JSONDecodeError as e:
            return json.dumps({"code": 400, "message": f"JSON解析失败: {e}", "data": None}, ensure_ascii=False)
        result = await erp_client.post("/api/orders/create", json_data=data)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def order_update(id: int, order_data: str) -> str:
        """更新采购订单。

        Args:
            id: 订单ID
            order_data: 更新的订单数据JSON字符串，格式同 order_create

        Returns:
            更新结果JSON
        """
        try:
            data = json.loads(order_data) if isinstance(order_data, str) else order_data
        except json.JSONDecodeError as e:
            return json.dumps({"code": 400, "message": f"JSON解析失败: {e}", "data": None}, ensure_ascii=False)
        result = await erp_client.put(f"/api/orders/update/{id}", json_data=data)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def order_page(
        current: int = 1,
        size: int = 10,
        order_number: str = None,
        status: int = None,
        start_date: str = None,
        end_date: str = None,
    ) -> str:
        """分页查询采购订单列表。

        Args:
            current: 当前页码，默认1
            size: 每页大小，默认10
            order_number: 订单编号（可选，模糊匹配）
            status: 订单状态（可选）：0=待审核,1=已审核,2=已发货,3=已收货,4=已完成
            start_date: 开始日期（可选），格式 yyyy-MM-dd
            end_date: 结束日期（可选），格式 yyyy-MM-dd

        Returns:
            分页订单数据JSON
        """
        params = {
            "current": current,
            "size": size,
            "orderNumber": order_number,
            "status": status,
            "startDate": start_date,
            "endDate": end_date,
        }
        result = await erp_client.get("/api/orders/page", params=params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def order_get(id: int) -> str:
        """获取单个采购订单的详细信息（含订单明细）。

        Args:
            id: 订单ID

        Returns:
            订单详细信息JSON，包含 orderNumber, totalAmount, status, orderTime, orderDetail[]
        """
        result = await erp_client.get(f"/api/orders/get/{id}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def order_search_details(
        part_name: str = None,
        start_date: str = None,
        end_date: str = None,
    ) -> str:
        """搜索订单明细，支持按零部件名称和时间范围过滤。

        Args:
            part_name: 零部件名称（可选，模糊匹配）
            start_date: 开始时间（可选），支持 yyyy-MM-dd 或 yyyy-MM-dd HH:mm:ss
            end_date: 结束时间（可选），支持 yyyy-MM-dd 或 yyyy-MM-dd HH:mm:ss

        Returns:
            订单明细列表JSON，每条包含零部件信息和供应商信息
        """
        params = {
            "partName": part_name,
            "startDate": start_date,
            "endDate": end_date,
        }
        result = await erp_client.get("/api/orders/search-details", params=params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def order_statistics(
        start_date: str = None,
        end_date: str = None,
    ) -> str:
        """获取采购统计数据。

        Args:
            start_date: 开始日期（可选），格式 yyyy-MM-dd
            end_date: 结束日期（可选），格式 yyyy-MM-dd

        Returns:
            采购统计JSON，包含订单总数、总金额、各状态数量等
        """
        params = {
            "startDate": start_date,
            "endDate": end_date,
        }
        result = await erp_client.get("/api/orders/statistics", params=params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def order_update_status(id: int, status: int) -> str:
        """更新订单状态。

        Args:
            id: 订单ID
            status: 新状态：0=待审核,1=已审核,2=已发货,3=已收货,4=已完成

        Returns:
            操作结果JSON
        """
        result = await erp_client.patch(
            f"/api/orders/update-status/{id}", params={"status": status}
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
