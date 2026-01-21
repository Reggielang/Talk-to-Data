"""BLOCK 节点 - 使用 LLM 进行问题分类和拦截."""

from app.graph.core.state import State
from loguru import logger
from app.conf.prompt_init import prompt_template_service
from app.services.llm_service import llm_service, LlmRequest
from langchain_core.messages import HumanMessage, SystemMessage


def block_node(state: State) -> State:
    """BLOCK 节点 - 使用 LLM 进行问题分类和拦截."""
    logger.info(f"BLOCK node: Checking query: {state['UserQuery']}")

    # 设置 state 到 llm_service，自动记录 LLM 调用
    llm_service.set_state(state)

    # 初始化拦截状态
    state["IsBlocked"] = False
    state["BlockReason"] = ""

    user_query = state["UserQuery"]

    try:
        # 1. 渲染提示词模板
        block_system_prompt = prompt_template_service.render("block_system.j2")
        block_user_prompt = prompt_template_service.render(
            "block_user.j2",
            messages=state.get("Messages", []),
            question=user_query,
        )
        
        # 2. 构建消息
        messages = [
            SystemMessage(content=block_system_prompt),
            HumanMessage(content=block_user_prompt),
        ]

        # 3. 调用 LLM JSON 输出
        request = LlmRequest(
            messages=messages,
            model_name=state["LlmModelName"],
            temperature=0.0,
        )

        #打印prompt
        logger.info(f"BLOCK System Prompt:\n {block_system_prompt}")
        logger.info(f"BLOCK User Prompt:\n {block_user_prompt}")

        result = llm_service.simple_json_output(request)

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
