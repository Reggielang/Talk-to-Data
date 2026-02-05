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
    messages: Optional[list[dict]] = Field(default_factory=list, description="历史消息列表")


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


# ============== Elasticsearch 索引管理 Schemas ==============

class ESIndexCreateRequest(BaseModel):
    """创建 ES 索引请求"""
    index_name: str = Field(..., description="索引名称", min_length=1, max_length=100)


class ESDocumentCreateRequest(BaseModel):
    """添加 ES 文档请求"""
    index_name: str = Field(..., description="索引名称")
    id: Optional[str] = Field(None, description="文档ID（不填则自动生成UUID）")
    question: str = Field(..., description="问题")
    content: str = Field(..., description="内容")
    auto_embedding: bool = Field(True, description="是否自动获取向量")


class ESIndexResponse(BaseModel):
    """ES 索引操作响应"""
    success: bool = Field(..., description="操作是否成功")
    index: Optional[str] = Field(None, description="索引名称")
    doc_id: Optional[str] = Field(None, description="文档ID")
    result: Optional[str] = Field(None, description="操作结果")
    error: Optional[str] = Field(None, description="错误信息")


class ESIndexInfoResponse(BaseModel):
    """ES 索引信息响应"""
    success: bool
    exists: Optional[bool] = None
    index: Optional[str] = None
    settings: Optional[dict] = None
    mappings: Optional[dict] = None
    stats: Optional[dict] = None
    error: Optional[str] = None
