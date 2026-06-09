"""LLM 服务 - 无状态设计，仅负责调用 LLM."""
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime
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
from app.graph.core.model import MessageItem


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
    """LLM 服务 - 无状态，线程安全."""

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

        logger.info(f"LlmService initialized with model: {self.model}")

    def simple_chat(self, request: LlmRequest) -> str:
        """简单聊天，返回 LLM 响应内容.

        注意：不再自动记录 LlmCalls，由调用方自行处理。
        """
        llm = self.llm
        model_name = request.model_name or self.model
        temperature = request.temperature or self.temperature

        try:
            response = llm.invoke(request.messages)

            # 处理 content
            content = response.content
            if isinstance(content, str):
                content = content.strip()
            else:
                content = str(content)

            return content

        except Exception as e:
            logger.error(f"LlmService.simple_chat error: {e}")
            raise

    def simple_json_output(self, request: LlmRequest) -> Dict[str, Any]:
        """JSON 输出，返回解析后的字典."""
        content = self.simple_chat(request)

        try:
            import json
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


# 全局单例（无状态，线程安全）
llm_service = LlmService()
