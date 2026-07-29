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
# 定义订单必填字段列表
# 这些字段在创建或更新订单时必须提供，否则数据不完整
# orderNumber: 订单编号（唯一标识）
# orderDetail: 订单明细列表（包含具体商品信息）
ORDER_REQUIRED_FIELDS = ["orderNumber", "orderDetail"]

# 定义订单明细必填字段列表
# 每个订单明细项必须包含以下三个字段
# partId: 商品/零件ID（标识具体商品）
# quantity: 订购数量（必须是正数）
# unitPrice: 商品单价（必须是正数）
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
    """解析用户补充的自由文本，提取结构化数据
    
    支持两种格式：
    1. JSON 格式：直接解析合并
    2. 自由文本：用正则提取关键字段
       例如 "零件ID=5 数量100 单价25.5" → {"orderDetail": [{"partId": 5, ...}]}
    """
    
    # ============ 第1步：复制当前数据（避免修改原始数据） ============
    # 将 current_data 复制一份，作为返回结果的基础
    # 这样既保留了已有数据，又不会影响外部传入的字典 current_data是原有的数据
    result = dict(current_data)
    
    # ============ 第2步：尝试 JSON 格式解析 ============
    # 先尝试把输入文本当作 JSON 字符串解析
    # 因为用户可能直接粘贴 JSON 格式的数据
    try:
        # 将 JSON 字符串解析为 Python 字典
        # 例如: '{"orderNumber": "ORD001", "quantity": 100}' → {"orderNumber": "ORD001", "quantity": 100}
        parsed = json.loads(text)
        
        # 检查解析结果是否为字典类型
        # 只有字典才能和当前数据合并
        if isinstance(parsed, dict):
            # 将解析出的数据更新到结果中
            # 如果字段已存在则覆盖，不存在则新增
            # 例如: result 有 "orderNumber"，parsed 有 "quantity" → 两者合并
            result.update(parsed)
            # JSON 解析成功，直接返回合并后的结果
            return result
            
    # 捕获 JSON 解析错误（非 JSON 格式或格式错误）
    except (json.JSONDecodeError, TypeError):
        # 解析失败则继续往下执行，尝试自由文本解析
        pass
    
    # ============ 第3步：自由文本正则解析 ============
    # 如果 JSON 解析失败，尝试从自然语言中提取关键信息
    
    # ----- 3.1 提取 partId（物料/零件 ID） -----
    # 正则表达式: r'(?:partId|物料\s*ID|零件\s*ID)[=:\s]*(\d+)'
    # 解释:
    #   (?:partId|物料\s*ID|零件\s*ID)  - 匹配关键词（不捕获分组）
    #     - partId: 英文字段名
    #     - 物料\s*ID: 中文"物料ID"或"物料 ID"
    #     - 零件\s*ID: 中文"零件ID"或"零件 ID"
    #   [=:\s]*  - 匹配分隔符：等号、冒号或空格（0个或多个）
    #   (\d+)    - 捕获组：匹配1个或多个数字（零件ID的值）
    # 
    # 匹配示例:
    #   "partId=123"      → 匹配 "123"
    #   "物料ID: 456"     → 匹配 "456"
    #   "零件 ID 789"     → 匹配 "789"
    part_id_match = re.search(r'(?:partId|物料\s*ID|零件\s*ID)[=:\s]*(\d+)', text, re.IGNORECASE)
    
    if part_id_match:
        # 如果匹配到 partId，将其添加到订单明细中
        # result.setdefault("orderDetail", [{}]) 的含义:
        #   - 如果 result 中有 "orderDetail" 字段，获取它的值
        #   - 如果没有，设置默认值为 [{}]（一个包含空字典的列表）
        # [0] 取列表中的第一个元素（第一个订单明细项）
        # ["partId"] = int(...) 设置 partId 字段，并转为整数
        # 
        # 这样做的目的是：如果 orderDetail 还不存在，自动创建它
        result.setdefault("orderDetail", [{}])[0]["partId"] = int(part_id_match.group(1))
    
    # ----- 3.2 提取 quantity（数量） -----
    # 正则表达式: r'(?:quantity|数量)[=:\s]*(\d+)'
    # 解释:
    #   (?:quantity|数量)  - 匹配关键词（不捕获分组）
    #     - quantity: 英文字段名
    #     - 数量: 中文字段名
    #   [=:\s]*  - 匹配分隔符：等号、冒号或空格
    #   (\d+)    - 捕获组：匹配1个或多个数字（数量的值）
    #
    # 匹配示例:
    #   "quantity=100"    → 匹配 "100"
    #   "数量: 200"       → 匹配 "200"
    qty_match = re.search(r'(?:quantity|数量)[=:\s]*(\d+)', text, re.IGNORECASE)
    
    if qty_match:
        # 将提取的数量添加到订单明细的第一项
        # 同样，如果 orderDetail 不存在则自动创建
        result.setdefault("orderDetail", [{}])[0]["quantity"] = int(qty_match.group(1))
    
    # ----- 3.3 提取 unitPrice（单价） -----
    # 正则表达式: r'(?:unitPrice|单价)[=:\s]*([\d.]+)'
    # 解释:
    #   (?:unitPrice|单价)  - 匹配关键词（不捕获分组）
    #     - unitPrice: 英文字段名
    #     - 单价: 中文字段名
    #   [=:\s]*  - 匹配分隔符：等号、冒号或空格
    #   ([\d.]+) - 捕获组：匹配数字和点号（支持小数）
    #     - \d 匹配数字
    #     - \. 匹配小数点
    #     - 例如: "25.5"、"100"、"99.99"
    #
    # 匹配示例:
    #   "unitPrice=25.5"  → 匹配 "25.5"
    #   "单价: 100"       → 匹配 "100"
    #   "单价 99.99"      → 匹配 "99.99"
    price_match = re.search(r'(?:unitPrice|单价)[=:\s]*([\d.]+)', text, re.IGNORECASE)
    
    if price_match:
        # 将提取的单价添加到订单明细的第一项，转为浮点数
        result.setdefault("orderDetail", [{}])[0]["unitPrice"] = float(price_match.group(1))
    
    # ============ 第4步：返回处理后的结果 ============
    # 将合并了提取数据的字典返回给调用者
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
