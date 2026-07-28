"""
Web 搜索工具
使用通义千问 API 的搜索增强能力实现网络搜索
"""
import os
import httpx
from langchain_core.tools import tool

from ..log_utils import agent_logger
from ..env_utils import get_env


@tool
def web_search(query: str) -> str:
    """搜索互联网获取实时信息。

    Args:
        query: 搜索查询内容，例如"摩托车火花塞市场价格趋势 2026"

    Returns:
        搜索结果摘要文本
    """
    api_key = get_env("DASHSCOPE_API_KEY", "")
    if not api_key:
        return "错误: 未配置 DASHSCOPE_API_KEY，无法执行网络搜索"

    try:
        # 使用通义千问的联网搜索能力
        response = httpx.post(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "qwen-plus",
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个搜索助手。请根据用户的查询，提供准确、有用的信息摘要。如果无法确定信息，请明确说明。回复使用中文。"
                    },
                    {
                        "role": "user",
                        "content": f"请搜索并总结以下信息：{query}"
                    }
                ],
                "enable_search": True,
                "temperature": 0.3,
                "max_tokens": 2000,
            },
            timeout=30,
        )

        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            agent_logger.info(f"Web search completed for: {query[:50]}")
            return content
        else:
            error = response.json().get("error", {}).get("message", str(response.status_code))
            return f"搜索失败: {error}"

    except httpx.TimeoutException:
        return "搜索超时，请稍后重试"
    except Exception as e:
        agent_logger.error(f"Web search error: {e}")
        return f"搜索异常: {str(e)}"
