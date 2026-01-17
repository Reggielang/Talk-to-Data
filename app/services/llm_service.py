"""LLM 服务"""
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pydantic import SecretStr
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    AIMessage,
)
from langchain_core.output_parsers import JsonOutputParser
from loguru import logger
from app.conf.config import settings
import json


class MessageRole(str, Enum):
    """消息角色."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class MessageItem:
    """消息项."""
    Content: str
    Role: str


@dataclass
class LlmCallItem:
    """LLM 调用记录."""
    Id: str
    ModelName: str
    Temperature: float
    Messages: List[MessageItem]
    StartAt: datetime
    EndAt: datetime
    DurationMs: int
    PromptTokens: int = 0
    CompletionTokens: int = 0
    TotalTokens: int = 0


@dataclass
class LlmRequest:
    """LLM 请求."""
    messages: List[BaseMessage]
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class MessageContainer:
    """消息容器."""

    def __init__(self):
        self.system_message: Optional[SystemMessage] = None
        self.messages: List[BaseMessage] = []

    def set_system_prompt(self, prompt: str) -> None:
        """设置系统提示."""
        self.system_message = SystemMessage(content=prompt)

    def append_message(self, message: BaseMessage) -> None:
        """添加消息."""
        self.messages.append(message)

    def append_user_message(self, content: str) -> None:
        """添加用户消息."""
        self.messages.append(HumanMessage(content=content))

    def append_assistant_message(self, content: str) -> None:
        """添加助手消息."""
        self.messages.append(AIMessage(content=content))

    def get_messages(self) -> List[BaseMessage]:
        """获取所有消息."""
        all_messages = []
        if self.system_message:
            all_messages.append(self.system_message)
        all_messages.extend(self.messages)
        return all_messages


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
        self.model = model or settings.default_llm
        self.temperature = temperature
        self.api_key = api_key or settings.zhipuai_api_key
        self.base_url = base_url or settings.base_url

        self.llm = ChatOpenAI(
            model=self.model,
            temperature=self.temperature,
            api_key=SecretStr(self.api_key),
            base_url=self.base_url,
        )

        logger.info(f"LlmService initialized with model: {self.model}")

    def simple_chat(self, request: LlmRequest) -> Tuple[str, Optional[Dict[str, Any]]]:
        """简单聊天."""
        # 复用已初始化的 LLM
        llm = self.llm

        response = llm.invoke(request.messages)
        # 处理 content 可能是字符串或列表的情况
        content = response.content
        if isinstance(content, str):
            content = content.strip()
        else:
            content = str(content)
        usage = None

        return content, usage

    def simple_json_output(self, request: LlmRequest) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """JSON 输出."""
        # 复用已初始化的 LLM（temperature=0）
        llm = self.llm

        try:
            parser = JsonOutputParser()
            chain = llm | parser
            result = chain.invoke(request.messages)
            return result, None
        except Exception as e:
            logger.error(f"simple_json_output error: {e}")
            # 尝试手动解析
            try:
                content, _ = self.simple_chat(request)
                if isinstance(content, str):
                    if content.startswith("```json"):
                        content = content[7:]
                    elif content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    result = json.loads(content.strip())
                    return result, None
                raise
            except Exception as e2:
                logger.error(f"manual json parse failed: {e2}")
                raise


# 全局实例
llm_service = LlmService()