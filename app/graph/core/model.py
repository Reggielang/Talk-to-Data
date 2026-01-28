"""图执行的数据模型定义."""

import uuid
from datetime import datetime, timezone
from typing import TypedDict, Literal, List


class MessageItem(TypedDict):
    """消息项"""
    Role: Literal["user", "assistant", "system", "tool"]
    Content: str


class QueryResultItem(TypedDict):
    """查询结果项"""
    tablename: str
    sql: str


class LlmCallItem(TypedDict):
    """LLM 调用项"""
    Id: str
    StartAt: datetime
    EndAt: datetime
    Messages: list[MessageItem]
    ModelName: str
    Temperature: float
    PromptTokens: int
    TotalTokens: int
    ComletionTokens: int
    DurationMs: int


def create_llm_call(
    messages: List[MessageItem],
    response_content: str,
    model_name: str,
    temperature: float,
    start_at: datetime,
    end_at: datetime,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
) -> LlmCallItem:
    """创建 LLM 调用记录.

    Args:
        messages: 消息列表
        response_content: LLM 响应内容
        model_name: 模型名称
        temperature: 温度
        start_at: 开始时间
        end_at: 结束时间
        prompt_tokens: 输入 token 数
        completion_tokens: 输出 token 数
        total_tokens: 总 token 数

    Returns:
        LlmCallItem 对象
    """
    duration_ms = int((end_at - start_at).total_seconds() * 1000)
    call_id = uuid.uuid4().hex

    # 添加助手回复到消息列表
    message_items = list(messages)  # 复制一份
    message_items.append(MessageItem(
        Role="assistant",
        Content=response_content,
    ))

    return LlmCallItem(
        Id=call_id,
        StartAt=start_at,
        EndAt=end_at,
        Messages=message_items,
        ModelName=model_name,
        Temperature=temperature,
        PromptTokens=prompt_tokens,
        TotalTokens=total_tokens,
        ComletionTokens=completion_tokens,
        DurationMs=duration_ms,
    )
