from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime


class ChatRequest(BaseModel):
    """聊天请求模型."""
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None


class ChatResponse(BaseModel):
    """聊天响应模型."""
    response: str
    sql: Optional[str] = None
    data: Optional[List[Dict[str, Any]]] = None
    execution_time: Optional[float] = None
    session_id: str


class QueryHistory(BaseModel):
    """查询历史模型."""
    id: int
    session_id: str
    user_query: str
    generated_sql: str
    execution_result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime


class TableSchema(BaseModel):
    """表结构模型."""
    table_name: str
    columns: List[str]
    description: Optional[str] = None
