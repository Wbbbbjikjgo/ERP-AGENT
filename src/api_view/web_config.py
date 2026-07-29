"""
MongoDB 连接配置
Motor AsyncIOMotorClient 连接.
"""
import os
from motor.motor_asyncio import AsyncIOMotorClient
from ..agent.env_utils import get_env

MONGODB_URI = get_env("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = get_env("MONGODB_DB_NAME", "erp_agent")

# 全局 Motor 客户端
_client: AsyncIOMotorClient = None


def get_mongo_client() -> AsyncIOMotorClient:
    """获取 MongoDB 异步客户端"""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGODB_URI)
    return _client


def get_db():
    """获取数据库实例"""
    return get_mongo_client()[MONGODB_DB_NAME]


async def close_mongo_client():
    """关闭 MongoDB 连接"""
    global _client
    if _client:
        _client.close()
        _client = None
