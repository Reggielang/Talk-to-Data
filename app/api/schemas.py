"""API 请求和响应的 Pydantic 模型."""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class LLMProvider(str, Enum):
    """LLM 提供商"""
    OPENAI = "openai"
    ZHIPUAI = "zhipuai"
    QWEN = "qwen"


class ChatRequest(BaseModel):
    """聊天请求模型"""
    query: str = Field(..., description="用户查询问题", min_length=1, max_length=2000)
    session_id: Optional[str] = Field(None, description="会话ID，如果为空则创建新会话")
    user_email: Optional[str] = Field("", description="用户邮箱")
    model_name: Optional[str] = Field("glm-4.6", description="LLM 模型名称")
    stream: Optional[bool] = Field(False, description="是否使用流式响应")


# ============== 新的响应结构模型 ==============

class EventMeta(BaseModel):
    """事件元数据"""
    RequestId: str = Field(..., description="请求ID")


class EventItem(BaseModel):
    """单个事件"""
    Stage: str = Field(..., description="阶段名称")
    Type: str = Field(..., description="事件类型")
    SessionId: str = Field(..., description="会话ID")
    SessionMessageId: str = Field(..., description="消息ID")
    StageOutput: Optional[dict] = Field(None, description="阶段输出")
    Message: Optional[dict] = Field(None, description="消息内容")


class EventData(BaseModel):
    """事件数据"""
    SessionId: str = Field(..., description="会话ID")
    SessionMessageId: str = Field(..., description="消息ID")
    Events: list[EventItem] = Field(default_factory=list, description="事件列表")


class ChatResponse(BaseModel):
    """聊天响应模型 - 新结构"""
    Meta: EventMeta
    Data: EventData


class SessionCreateRequest(BaseModel):
    """创建会话请求"""
    user_sid: str = Field(..., description="用户会话ID")
    user_email: str = Field(..., description="用户邮箱")
    note: Optional[str] = Field(None, description="备注")


class SessionResponse(BaseModel):
    """会话响应"""
    session_id: str
    user_sid: str
    user_email: str
    note: Optional[str]
    created_at: datetime
    updated_at: datetime
    expired_at: datetime


class MessageResponse(BaseModel):
    """消息响应"""
    id: str
    session_id: str
    role: str
    content: str
    created_at: datetime
    updated_at: datetime


class EventResponse(BaseModel):
    """事件响应"""
    id: str
    session_id: str
    session_message_id: str
    node_name: str
    event_type: str
    event_body: dict[str, Any]
    created_at: datetime
    has_error: bool
    duration_ms: int


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str = Field(..., description="错误信息")
    detail: Optional[str] = Field(None, description="详细信息")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    timestamp: datetime
    version: str = "0.1.0"
