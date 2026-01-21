"""图执行事件模型 - 参考 Go 版本的 event.go"""

from typing import TypedDict, Optional, Any
import datetime
from app.graph.core.model import MessageItem, LlmCallItem
from app.graph.core.state import State
from loguru import logger


class EventType:
    """事件类型 - 参考 Go 版本的 dto.EventType"""
    START = "start"
    END = "end"
    TEXT_DELTA = "text_delta"
    TEXT_START = "text_start"
    TEXT_END = "text_end"
    TOOL_INPUT_START = "tool_input_start"
    TOOL_INPUT_END = "tool_input_end"
    ERROR = "error"


class StageOutput(TypedDict, total=False):
    """阶段输出 - 参考 Go 版本的 dto.StageOutput，所有字段可选"""
    QuestionVerifiedType: Optional[str]
    SupervisorToolCalls: Optional[list[dict]]
    SqlGenResult: Optional[dict]
    DataQueryResult: Optional[dict]
    PostProcessResult: Optional[dict]
    TableGenResult: Optional[dict]
    ChartGenResult: Optional[dict]
    # 可以根据需要添加更多字段


class Event(TypedDict, total=False):
    """图执行事件 - 参考 Go 版本的 core.Event，所有字段可选"""
    NodeName: str
    Type: str
    StageOutput: Optional[StageOutput]
    Message: Optional[MessageItem]
    Error: Optional[str]
    CurrentState: Optional[dict]
    LlmCalls: list[LlmCallItem]
    Timestamp: datetime.datetime


class EventCollector:
    """事件收集器 - 参考 Go 版本的事件收集机制

    通过回调机制自动收集事件，与节点实现完全解耦。
    """

    def __init__(self):
        self.events: list[dict] = []

    def get_events(self) -> list[dict]:
        """获取所有事件"""
        return self.events

    def get_llm_call_stats(self) -> dict:
        """获取 LLM 调用统计 - 参考 Go 版本的 GetLlmCallStats"""
        all_calls: list[LlmCallItem] = []
        for event in self.events:
            all_calls.extend(event.get("LlmCalls", []))

        if not all_calls:
            return {
                "total_calls": 0,
                "total_tokens": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_duration_ms": 0,
            }

        return {
            "total_calls": len(all_calls),
            "total_tokens": sum(call.get("TotalTokens", 0) for call in all_calls),
            "total_prompt_tokens": sum(call.get("PromptTokens", 0) for call in all_calls),
            "total_completion_tokens": sum(call.get("ComletionTokens", 0) for call in all_calls),
            "total_duration_ms": sum(call.get("DurationMs", 0) for call in all_calls),
        }

    def clear(self):
        """清空事件"""
        self.events.clear()


def create_event_collector() -> EventCollector:
    """创建新的事件收集器"""
    return EventCollector()
