from typing import TypedDict, Annotated, Literal
import operator
import datetime
from app.graph.core.model import LlmCallItem, MessageItem

class State(TypedDict):
    """对话状态"""
    SessionId: str
    SessionMessgeId: str
    UserQuery: str
    LlmModelName: str
    LlmTemperature: float
    Messages: Annotated[list[MessageItem], operator.add]
    SupervisorMessages:  Annotated[list[MessageItem], operator.add]
    CurrentDatetime: datetime.datetime
    LlmCalls: list[LlmCallItem]
    ForceEnd: bool
    IsBlocked: bool
    BlockReason: str
    UnderstandResult: dict[str, str]
    Response: str