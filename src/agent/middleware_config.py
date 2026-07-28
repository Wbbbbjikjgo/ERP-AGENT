"""
子Agent中间件工厂
为 analyst / order 子Agent 提供专用中间件配置
"""
from deepagents.middleware import SummarizationToolMiddleware


def get_analyst_middleware() -> list:
    """获取采购分析子Agent的中间件列表"""
    return [
        # 分析子Agent需要摘要工具来压缩大量数据结果
        SummarizationToolMiddleware(),
    ]


def get_order_middleware() -> list:
    """获取采购订单子Agent的中间件列表"""
    return [
        # 订单子Agent也需要摘要能力
        SummarizationToolMiddleware(),
    ]
