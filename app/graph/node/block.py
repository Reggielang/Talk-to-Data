"""BLOCK 节点 - 使用 LLM 进行问题分类和拦截."""

from datetime import datetime, timezone
from app.graph.core.state import State
from loguru import logger
from app.conf.prompt_init import prompt_template_service
from app.services.llm_service import llm_service, LlmRequest, convert_to_message_items
from app.graph.core.model import create_llm_call
from langchain_core.messages import HumanMessage, SystemMessage

# 历史消息保留长度
HISTORY_LENGTH = 4


def block_node(state: State) -> State:
    """BLOCK 节点 - 使用 LLM 进行问题分类和拦截."""
    logger.info(f"BLOCK node: Checking query: {state['UserQuery']}")

    # 初始化拦截状态
    state["IsBlocked"] = False
    state["BlockReason"] = ""

    user_query = state["UserQuery"]

    # 只保留 user 消息，并限制历史长度
    all_messages = state.get("Messages", [])

   
    # 过滤只保留 user 消息
    user_messages = [msg for msg in all_messages if msg.get("role") == "user"]

    logger.info(f"[BLOCK] Filtered to {len(user_messages)} user messages")

    # 只保留最近 HISTORY_LENGTH 条消息
    if len(user_messages) > HISTORY_LENGTH:
        user_messages = user_messages[-HISTORY_LENGTH:]
        logger.info(f"[BLOCK] Trimmed to last {HISTORY_LENGTH} user messages")

    try:
        # 1. 渲染提示词模板
        block_system_prompt = prompt_template_service.render("block_system.j2")
        block_user_prompt = prompt_template_service.render(
            "block_user.j2",
            messages=user_messages,
            question=user_query,
        )

        # 2. 构建消息
        messages = [
            SystemMessage(content=block_system_prompt),
            HumanMessage(content=block_user_prompt),
        ]

        # 3. 调用 LLM JSON 输出（手动记录 LLM 调用）
        start_at = datetime.now(timezone.utc)

        request = LlmRequest(
            messages=messages,
            model_name=state["LlmModelName"],
            temperature=0.0,
        )

        # 打印prompt
        logger.info(f"BLOCK System Prompt:\n {block_system_prompt}")
        logger.info(f"BLOCK User Prompt:\n {block_user_prompt}")

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
        # 4. 解析结果
        category = result.get("category", "relevant")
        message = result.get("message", "")

        # 5. 根据分类决定是否拦截
        if category in ["irrelevant", "unclear", "salary"]:
            state["IsBlocked"] = True
            state["BlockReason"] = message or f"问题分类为: {category}"
            logger.warning(f"Query blocked: {category}")
        else:
            state["IsBlocked"] = False
            logger.info("Query passed BLOCK check")

    except Exception as e:
        logger.error(f"BLOCK node error: {e}")
        state["IsBlocked"] = False
        state["BlockReason"] = f"分类失败: {str(e)}"

    return state
