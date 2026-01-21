"""LLM 服务"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import time
import uuid
from pydantic import SecretStr
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    AIMessage,
)
from loguru import logger
from app.conf.config import settings
from app.graph.core.model import LlmCallItem, MessageItem
from app.graph.core.state import State
import json


@dataclass
class LlmRequest:
    """LLM 请求."""
    messages: List[BaseMessage]
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


def convert_to_message_items(messages: List[BaseMessage]) -> List[MessageItem]:
    """将 LangChain 消息转换为 MessageItem."""
    message_items = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            role: str = "system"
        elif isinstance(msg, HumanMessage):
            role = "user"
        elif isinstance(msg, AIMessage):
            role = "assistant"
        else:
            role = "user"

        content = msg.content if isinstance(msg.content, str) else str(msg.content)

        message_items.append(MessageItem(
            Role=role,
            Content=content,
        ))
    return message_items


class LlmService:
    """LLM 服务."""

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.1,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """初始化 LLM 服务."""
        self.model = model or settings.qwen_model_name
        self.temperature = temperature
        self.api_key = api_key or settings.qwen_api_key
        self.base_url = base_url or settings.qwen_base_url

        self.llm = ChatOpenAI(
            model=self.model,
            temperature=self.temperature,
            api_key=SecretStr(self.api_key),
            base_url=self.base_url,
        )

        self._state: Optional[State] = None

        logger.info(f"LlmService initialized with model: {self.model}")

    def set_state(self, state: State):
        """设置当前处理的 state，用于自动记录 LLM 调用."""
        self._state = state

    def _create_and_record_llm_call(
        self,
        call_id: str,
        start_at: datetime,
        end_at: datetime,
        message_items: List[MessageItem],
        response_content: str,
        model_name: str,
        temperature: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
    ):
        """创建并记录 LLM 调用."""
        duration_ms = int((end_at - start_at).total_seconds() * 1000)

        # 添加助手回复到消息列表
        message_items.append(MessageItem(
            Role="assistant",
            Content=response_content,
        ))

        # 创建 LLM 调用记录
        llm_call_item = LlmCallItem(
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

        # 自动记录到 state
        if self._state is not None:
            self._state["LlmCalls"].append(llm_call_item)

    def simple_chat(self, request: LlmRequest) -> str:
        """简单聊天，自动记录到 state."""
        start_at = datetime.now()
        call_id = uuid.uuid4().hex

        llm = self.llm
        model_name = request.model_name or self.model
        temperature = request.temperature or self.temperature

        # 转换消息
        message_items = convert_to_message_items(request.messages)

        try:
            response = llm.invoke(request.messages)
            end_at = datetime.now()

            # 处理 content
            content = response.content
            if isinstance(content, str):
                content = content.strip()
            else:
                content = str(content)

            # 获取 token 使用情况
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0

            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                prompt_tokens = response.usage_metadata.get('input_tokens', 0)
                completion_tokens = response.usage_metadata.get('output_tokens', 0)
                total_tokens = response.usage_metadata.get('total_tokens', 0)

            # 创建并记录 LLM 调用
            self._create_and_record_llm_call(
                call_id=call_id,
                start_at=start_at,
                end_at=end_at,
                message_items=message_items,
                response_content=content,
                model_name=model_name,
                temperature=temperature,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )

            return content

        except Exception as e:
            end_at = datetime.now()
            logger.error(f"simple_chat error: {e}")

            # 即使出错也记录
            self._create_and_record_llm_call(
                call_id=call_id,
                start_at=start_at,
                end_at=end_at,
                message_items=message_items,
                response_content=str(e),
                model_name=model_name,
                temperature=temperature,
            )

            raise

    def simple_json_output(self, request: LlmRequest) -> Dict[str, Any]:
        """JSON 输出，自动记录到 state."""
        content = self.simple_chat(request)

        try:
            return json.loads(content)
        except Exception as e:
            logger.error(f"尝试手动提取 JSON 代码块: {e}")
            # 尝试提取 JSON 代码块
            try:
                if content.startswith("```json"):
                    content = content[7:]
                elif content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                return json.loads(content.strip())
            except Exception as e2:
                logger.error(f"manual json parse failed: {e2}")
                raise


# 全局实例
llm_service = LlmService()
