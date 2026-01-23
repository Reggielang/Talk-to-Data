"""Summary 节点 - 对数据查询和处理结果进行总结分析."""

import json
from datetime import datetime
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from loguru import logger

from app.graph.core.state import State
from app.conf.prompt_init import PromptConfig
from app.conf.utils.prompt_parms import create_date_function
from app.services.llm_service import llm_service, LlmRequest


def summary_node(state: State) -> State:
    """Summary 节点 - 对数据查询和处理结果进行总结分析.

    Args:
        state: 对话状态

    Returns:
        更新后的 State
    """

    # 检查是否被拦截
    if state.get("IsBlocked", False):
        logger.info("Query is blocked, skipping Summary node.")
        return state

    # 设置 state 到 llm_service，自动记录 LLM 调用
    llm_service.set_state(state)


    try:
        dataset_id = state.get("SummarizeDatasetId", "")
        user_query = state.get("UserQuery", "")

        logger.info(f"Summary dataset_id: {dataset_id}")

        # 获取数据集信息
        datasets = state.get("Datasets", {})
        dataset = datasets.get(dataset_id, {})

        # 构建总结提示
        prompt_config = PromptConfig()

        # 获取数据内容
        data_content = dataset.get("SampleData", "")
        if not data_content and state.get("DataQueryResult"):
            data_content = state["DataQueryResult"].get("SampleData", "")

        system_prompt = prompt_config.render(
            "summary_system.j2"
        )

        user_prompt = f"用户问题: {user_query}\n\n"
        if data_content:
            user_prompt += f"数据:\n```\n{data_content}\n```\n\n"
        user_prompt += "请根据以上数据回答用户问题。"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        logger.info(f"Summary System Prompt:\n {system_prompt}")

        request = LlmRequest(
            messages=messages,
            model_name=state.get("LlmModelName"),
            temperature=0.3,
        )

        summary_result = llm_service.simple_chat(request)

        state["SummarizeResult"] = summary_result
        logger.info(f"Summary User Prompt:\n {user_prompt}")
        logger.info(f"Summary node completed:\n {summary_result}")

    except Exception as e:
        logger.error(f"Summary node error: {e}")

    return state
