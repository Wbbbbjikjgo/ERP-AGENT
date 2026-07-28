"""
历史会话管理
会话列表 / 消息查询 / 会话删除
"""
from fastapi import APIRouter, Query

from ..agent_loader import agent_loader

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
async def list_conversations(user_id: str = Query(default="default_user")):
    """获取会话列表"""
    conversations = await agent_loader.get_conversations(user_id)
    return {"conversations": conversations}


@router.get("/{thread_id}/messages")
async def get_messages(thread_id: str):
    """获取指定会话的消息列表"""
    messages = await agent_loader.get_display_messages(thread_id)
    return {"thread_id": thread_id, "messages": messages}


@router.delete("/{thread_id}")
async def delete_conversation(thread_id: str):
    """删除会话"""
    await agent_loader.delete_conversation(thread_id)
    return {"success": True, "message": f"会话 {thread_id} 已删除"}
