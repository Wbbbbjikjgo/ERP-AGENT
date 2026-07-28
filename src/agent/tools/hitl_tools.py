"""
HITL 人工介入工具
request_order_info - 当订单必填字段缺失时，向用户请求补充信息
"""
import json
import re
from typing import Optional
from langchain_core.tools import tool
from langgraph.types import interrupt

from ..log_utils import agent_logger

# 订单必填字段
ORDER_REQUIRED_FIELDS = ["orderNumber", "orderDetail"]
ORDER_DETAIL_REQUIRED_FIELDS = ["partId", "quantity", "unitPrice"]


def validate_order_data(data: dict) -> list:
    """校验订单数据，返回缺失字段列表"""
    missing = []
    for field in ORDER_REQUIRED_FIELDS:
        if field not in data or data[field] is None:
            missing.append(field)

    if "orderDetail" in data and data["orderDetail"]:
        for i, detail in enumerate(data["orderDetail"]):
            for field in ORDER_DETAIL_REQUIRED_FIELDS:
                if field not in detail or detail[field] is None:
                    missing.append(f"orderDetail[{i}].{field}")
    elif "orderDetail" not in missing:
        missing.append("orderDetail (至少需要一条明细)")

    return missing


def parse_supplement_text(text: str, current_data: dict) -> dict:
    """解析用户补充的自由文本，提取结构化数据"""
    result = dict(current_data)

    # 尝试解析为 JSON
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            result.update(parsed)
            return result
    except (json.JSONDecodeError, TypeError):
        pass

    # 从自由文本中提取关键信息
    # 匹配 partId / 物料ID / 零件ID
    part_id_match = re.search(r'(?:partId|part_id|物料\s*ID|零件\s*ID|零部件\s*ID)[=:\s]*(\d+)', text, re.IGNORECASE)
    if part_id_match:
        if "orderDetail" not in result or not result["orderDetail"]:
            result["orderDetail"] = [{}]
        result["orderDetail"][0]["partId"] = int(part_id_match.group(1))

    # 匹配 quantity / 数量
    qty_match = re.search(r'(?:quantity|数量|数\s*量)[=:\s]*(\d+)', text, re.IGNORECASE)
    if qty_match:
        if "orderDetail" not in result or not result["orderDetail"]:
            result["orderDetail"] = [{}]
        result["orderDetail"][0]["quantity"] = int(qty_match.group(1))

    # 匹配 unitPrice / 单价
    price_match = re.search(r'(?:unitPrice|unit_price|单价|价\s*格)[=:\s]*([\d.]+)', text, re.IGNORECASE)
    if price_match:
        if "orderDetail" not in result or not result["orderDetail"]:
            result["orderDetail"] = [{}]
        result["orderDetail"][0]["unitPrice"] = float(price_match.group(1))

    # 匹配 orderNumber / 订单编号
    order_num_match = re.search(r'(?:orderNumber|order_number|订单编号|编\s*号)[=:\s]*([A-Za-z0-9]+)', text, re.IGNORECASE)
    if order_num_match:
        result["orderNumber"] = order_num_match.group(1)

    return result


@tool
def request_order_info(extracted_data: str, missing_fields: str) -> str:
    """当订单必填字段缺失时，向用户请求补充信息。此工具会暂停执行等待用户输入。

    Args:
        extracted_data: 当前已提取的订单数据JSON字符串
        missing_fields: 缺失字段列表JSON字符串，例如 ["partId", "quantity"]

    Returns:
        完整的订单数据JSON（所有必填字段已填充）
    """
    try:
        data = json.loads(extracted_data) if isinstance(extracted_data, str) else extracted_data
    except json.JSONDecodeError:
        data = {}

    try:
        missing = json.loads(missing_fields) if isinstance(missing_fields, str) else missing_fields
    except json.JSONDecodeError:
        missing = []

    agent_logger.info(f"Requesting order info supplement. Missing: {missing}")

    # 循环：校验 → 中断等待补充 → 解析 → 校验 ... 直到完整
    max_rounds = 5
    for round_num in range(max_rounds):
        if not missing:
            return json.dumps(data, ensure_ascii=False, indent=2)

        # 触发中断，等待用户补充
        supplement = interrupt({
            "type": "order_info_request",
            "missing_fields": missing,
            "current_data": data,
            "message": f"请补充以下订单信息: {', '.join(missing)}",
        })

        # 解析用户补充内容
        supplement_text = ""
        if isinstance(supplement, dict):
            supplement_text = supplement.get("supplement", "")
        elif isinstance(supplement, str):
            supplement_text = supplement

        # 合并数据
        data = parse_supplement_text(supplement_text, data)

        # 重新校验
        missing = validate_order_data(data)
        agent_logger.info(f"Round {round_num + 1}: still missing {missing}")

    # 超过最大轮次
    if missing:
        return json.dumps({
            "error": f"经过{max_rounds}轮补充仍有字段缺失: {missing}",
            "current_data": data,
        }, ensure_ascii=False)

    return json.dumps(data, ensure_ascii=False, indent=2)
