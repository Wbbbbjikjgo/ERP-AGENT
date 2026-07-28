"""
数据模型定义
ProcurementContext、UserPreferences、ChatRequest 等 Pydantic 模型
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class UserPreferences(BaseModel):
    """用户偏好模型"""
    preferred_output: str = Field(default="markdown", description="首选输出格式: markdown/table/json")
    preferred_chart_type: str = Field(default="bar", description="首选图表类型: bar/line/pie/scatter等")
    preferred_currency: str = Field(default="CNY", description="首选货币单位")
    preferred_language: str = Field(default="zh", description="首选语言: zh/en")
    recent_suppliers: List[str] = Field(default_factory=list, description="最近查询的供应商")
    recent_queries: List[str] = Field(default_factory=list, description="最近的查询记录")


class ProcurementContext(BaseModel):
    """采购上下文 - 每次请求注入到 Agent state"""
    user_id: str = Field(default="default_user", description="用户ID")
    username: str = Field(default="用户", description="用户名")
    preferences: dict = Field(default_factory=dict, description="用户偏好字典")
    session_start: str = Field(default_factory=lambda: datetime.now().isoformat())


class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str = Field(..., description="用户消息内容")
    thread_id: str = Field(default=None, description="会话线程ID，为空则创建新会话")
    user_id: str = Field(default="default_user", description="用户ID")
    username: str = Field(default="用户", description="用户名")


class ResumeRequest(BaseModel):
    """中断恢复请求模型"""
    resume: dict = Field(..., description="恢复数据，格式取决于中断类型")


class SSEEvent(BaseModel):
    """SSE 事件模型"""
    event: str = Field(..., description="事件类型: token/tool_start/tool_args/tool_result/tool_end/interrupt/done")
    data: dict = Field(default_factory=dict, description="事件数据")


class ConversationRecord(BaseModel):
    """会话记录"""
    thread_id: str
    user_id: str
    title: str = "新对话"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class DisplayMessage(BaseModel):
    """前端展示消息"""
    role: str = Field(..., description="角色: user/assistant/tool")
    content: str = Field(default="", description="消息内容")
    tool_calls: Optional[List[dict]] = Field(default=None, description="工具调用信息")
    source: Optional[str] = Field(default=None, description="来源: main/analyst/order")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
