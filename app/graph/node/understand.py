"""Understand 节点 - 使用 LLM 进行问题澄清."""

from datetime import datetime, timezone
from app.graph.core.state import State
from loguru import logger
from app.conf.prompt_init import prompt_template_service
from app.services.llm_service import llm_service, LlmRequest
from app.graph.core.model import create_llm_call
from app.services.llm_service import convert_to_message_items
from langchain_core.messages import HumanMessage, SystemMessage

# 历史消息保留长度
HISTORY_LENGTH = 4


def understand_node(state: State) -> State:
    """Understand 节点 - 使用 LLM 进行问题澄清."""
    logger.info(f"Understand node: Checking query: {state['UserQuery']}")

    if state.get("IsBlocked", False):
        logger.info("Query is blocked, skipping Understand node.")
        return state

    user_query = state["UserQuery"]

    # 只保留 user 消息，并限制历史长度
    all_messages = state.get("Messages", [])

    # 过滤只保留 user 消息
    user_messages = [msg for msg in all_messages if msg.get("role") == "user"]

    logger.info(f"[Understand] Filtered to {len(user_messages)} user messages")

    # 只保留最近 HISTORY_LENGTH 条消息
    if len(user_messages) > HISTORY_LENGTH:
        user_messages = user_messages[-HISTORY_LENGTH:]
        logger.info(f"[Understand] Trimmed to last {HISTORY_LENGTH} user messages")

    try:
        # 1. 渲染提示词模板
        understand_system_prompt = prompt_template_service.render("understand_system.j2")

        understand_user_prompt = prompt_template_service.render(
            "understand_user.j2",
            messages=user_messages,
            question=user_query,
        )

        # 2. 构建消息
        messages = [
            SystemMessage(content=understand_system_prompt),
            HumanMessage(content=understand_user_prompt),
        ]
        #打印prompt
        logger.info(f"Understand System Prompt:\n {understand_system_prompt}")
        logger.info(f"Understand User Prompt:\n {understand_user_prompt}")

        # 3. 调用 LLM JSON 输出（手动记录 LLM 调用）
        start_at = datetime.now(timezone.utc)

        request = LlmRequest(
            messages=messages,
            model_name=state["LlmModelName"],
            temperature=0.0,
        )

        result = llm_service.simple_json_output(request)

        end_at = datetime.now(timezone.utc)

        # 记录 LLM 调用到 state
        llm_call = create_llm_call(
            messages=convert_to_message_items(messages),
            response_content=str(result),
            model_name=state["LlmModelName"],
            temperature=0.0,
            start_at=start_at,
            end_at=end_at,
        )
        state["LlmCalls"].append(llm_call)

        logger.info(f"LLM message: {result}")
        # 4.更新State
        state["UnderstandResult"] = result

        # 设置 RephraseResult 供 data_query_node 使用
        rephrase = result.get("question", user_query)
        state["RephraseResult"] = rephrase
        logger.info(f"RephraseResult: {rephrase}")

    except Exception as e:
        logger.error(f"Understand node error: {e}")
        # 出错时使用原始查询作为 RephraseResult
        state["RephraseResult"] = user_query

    return state
