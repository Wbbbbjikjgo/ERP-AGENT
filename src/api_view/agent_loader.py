"""
AgentLoader 单例
持有 agent 实例、MongoDB 连接、create_config、save/get_display_messages
"""
import uuid
from typing import Optional
from datetime import datetime

from ..agent.log_utils import web_logger
from ..agent.schema import ProcurementContext
from .web_config import get_db


class AgentLoader:
    """Agent 加载器单例 - 管理 Agent 生命周期"""

    _instance: Optional['AgentLoader'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.agent = None
        self._checkpointer = None
        self._store = None
        web_logger.info("AgentLoader initialized")

    async def initialize(self):
        """初始化 Agent（延迟加载）"""
        if self.agent is not None:
            return

        web_logger.info("Initializing agent...")
        try:
            from langgraph.checkpoint.memory import MemorySaver
            from langgraph.store.memory import InMemoryStore

            # 开发阶段使用内存存储，生产环境替换为 MongoDB
            self._checkpointer = MemorySaver()
            self._store = InMemoryStore()

            from ..agent.main_agent import create_main_agent
            context = ProcurementContext()
            self.agent = create_main_agent(
                user_context=context,
                checkpointer=self._checkpointer,
                store=self._store,
            )
            web_logger.info("Agent initialized successfully")
        except Exception as e:
            web_logger.error(f"Failed to initialize agent: {e}")
            raise

    def create_config(self, thread_id: str) -> dict:
        """创建 LangGraph 运行配置"""
        return {
            "configurable": {
                "thread_id": thread_id,
            }
        }

    def generate_thread_id(self) -> str:
        """生成新的会话线程ID"""
        return str(uuid.uuid4())

    async def save_display_messages(self, thread_id: str, messages: list):
        """保存前端展示消息到 MongoDB"""
        db = get_db()
        await db.display_messages.update_one(
            {"thread_id": thread_id},
            {"$set": {"messages": messages, "updated_at": datetime.now().isoformat()}},
            upsert=True,
        )

    async def get_display_messages(self, thread_id: str) -> list:
        """获取前端展示消息"""
        db = get_db()
        doc = await db.display_messages.find_one({"thread_id": thread_id})
        return doc.get("messages", []) if doc else []

    async def save_conversation(self, thread_id: str, user_id: str, title: str = "新对话"):
        """保存/更新会话记录"""
        db = get_db()
        await db.conversations.update_one(
            {"thread_id": thread_id},
            {"$set": {"user_id": user_id, "title": title, "updated_at": datetime.now().isoformat()},
             "$setOnInsert": {"created_at": datetime.now().isoformat()}},
            upsert=True,
        )

    async def get_conversations(self, user_id: str) -> list:
        """获取用户的会话列表"""
        db = get_db()
        cursor = db.conversations.find({"user_id": user_id}).sort("updated_at", -1)
        conversations = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            conversations.append(doc)
        return conversations

    async def delete_conversation(self, thread_id: str):
        """删除会话"""
        db = get_db()
        await db.conversations.delete_one({"thread_id": thread_id})
        await db.display_messages.delete_one({"thread_id": thread_id})


# 全局单例
agent_loader = AgentLoader()
