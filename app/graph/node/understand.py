"""Understand 节点 - 使用 LLM 进行问题澄清."""

from app.graph.core.state import State
from loguru import logger
from app.conf.prompt_init import prompt_template_service
from app.services.llm_service import llm_service, LlmRequest
from langchain_core.messages import HumanMessage, SystemMessage


def understand_node(state: State) -> State:
    """Understand 节点 - 使用 LLM 进行问题澄清."""
    logger.info(f"Understand node: Checking query: {state['UserQuery']}")
    
    if state.get("IsBlocked", False):
        logger.info("Query is blocked, skipping Understand node.")
        return state
    
    user_query = state["UserQuery"]

    try:
        # 1. 渲染提示词模板
        understand_system_prompt = prompt_template_service.render("understand_system.j2")

        understand_user_prompt = prompt_template_service.render(
            "understand_user.j2",
            messages=state.get("Messages", []),
            question=user_query,
        )

        # 2. 构建消息
        messages = [
            SystemMessage(content=understand_system_prompt),
            HumanMessage(content=understand_user_prompt),
        ]
                #打印prompt
        logger.info(f"Understand System Prompt: {understand_system_prompt}")
        logger.info(f"Understand User Prompt: {understand_user_prompt}")

        # 3. 调用 LLM JSON 输出
        request = LlmRequest(
            messages=messages,
            model_name=state["LlmModelName"],
            temperature=0.0,
        )

        result, _ = llm_service.simple_json_output(request)

        logger.info(f"LLM message: {result}")
        # 4.更新State
        state["UnderstandResult"] = result

    except Exception as e:
        logger.error(f"Understand node error: {e}")
        
    return state