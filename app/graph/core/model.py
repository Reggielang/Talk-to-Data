from typing import TypedDict, Annotated, Literal
import datetime
class MessageItem(TypedDict):
    """消息项"""
    Id: str
    Role: Literal["user", "assistant", "system","tool"]
    Content: str
    Error: Exception | None
    FirstTokenAt: float | None


class QueryResultItem(TypedDict):
    """查询结果项"""
    tablename: str
    sql: str

class LlmCallItem(TypedDict):
    """LLM 调用项"""
    Id: str
    StartAt: datetime.datetime
    EndAt: datetime.datetime
    Messages: list[MessageItem]
    ModelName: str
    Temperature: float
    PromptTokens: int
    TotalTokens: int
    ComletionTokens: int
    DurationMs: int
    FirstTokenMs: int