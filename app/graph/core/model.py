from typing import TypedDict, Annotated, Literal
import datetime
class MessageItem(TypedDict):
    """消息项"""
    Role: Literal["user", "assistant", "system","tool"]
    Content: str


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