"""Supervisor 节点 - 分析用户请求，选择合适的工具."""

import json
import re
from datetime import datetime
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from app.graph.core.state import State
from app.conf.prompt_init import PromptConfig
from app.conf.utils.prompt_parms import create_date_function
from app.services.llm_service import llm_service, LlmRequest


class ToolUse:
    """工具调用"""

    def __init__(self, name: str, arguments: dict):
        self.name = name
        self.arguments = arguments

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "arguments": self.arguments
        }


class SupervisorToolUseOutput:
    """Supervisor 工具调用输出"""

    def __init__(self, tool_use: ToolUse):
        self.tool_use = tool_use

    def validate(self) -> tuple[bool, str]:
        """验证工具调用"""
        if self.tool_use.name == "":
            return False, "你必须调用一个工具"

        if self.tool_use.name == "query_data":
            table = self.tool_use.arguments.get("table")
            if not isinstance(table, str) or not table:
                return False, "query_data 工具需要一个 table 参数，类型为字符串"

        elif self.tool_use.name == "postprocess":
            dataset_id = self.tool_use.arguments.get("dataset_id")
            if not isinstance(dataset_id, str) or not dataset_id:
                return False, "postprocess 工具需要 dataset_id 参数，类型为字符串"

        elif self.tool_use.name == "summarize":
            dataset_id = self.tool_use.arguments.get("dataset_id")
            if not isinstance(dataset_id, str) or not dataset_id:
                return False, "summarize 工具需要 dataset_id 参数，类型为字符串"
            if "," in dataset_id:
                return False, "summarize 工具只允许传入唯一一个数据集ID"

        return True, ""


def route_from_supervisor(state: State) -> str:
    """根据 Supervisor 的工具调用结果决定下一步路由.

    Returns:
        目标节点名称: "query_data", "postprocess", "summarize", 或 "end"
    """
    # 根据 DataQueryTask 判断是否需要查询数据
    if state.get("DataQueryTask"):
        return "query_data"

    # 根据 PostProcessTask 判断是否需要后处理
    if state.get("PostProcessTask"):
        return "postprocess"

    # 根据 SummarizeDatasetId 判断是否需要总结
    if state.get("SummarizeDatasetId"):
        return "summarize"

    # 默认结束
    return "end"


def extract_tool_use_from_content(content: str) -> Optional[ToolUse]:
    """从 LLM 输出中提取工具调用"""
    # 尝试提取 JSON 代码块
    json_pattern = r'```json\s*(\{.*?\})\s*```'
    matches = re.findall(json_pattern, content, re.DOTALL)
    if matches:
        try:
            data = json.loads(matches[0])
            if "tool_use" in data:
                tool_use_data = data["tool_use"]
                return ToolUse(
                    name=tool_use_data.get("name", ""),
                    arguments=tool_use_data.get("arguments", {})
                )
        except json.JSONDecodeError:
            pass

    # 尝试直接解析 JSON
    try:
        data = json.loads(content.strip())
        if "tool_use" in data:
            tool_use_data = data["tool_use"]
            return ToolUse(
                name=tool_use_data.get("name", ""),
                arguments=tool_use_data.get("arguments", {})
            )
    except json.JSONDecodeError:
        pass

    return None


def supervisor_node(state: State) -> State:
    """Supervisor 节点 - 分析用户请求，选择合适的工具.

    Args:
        state: 对话状态

    Returns:
        更新后的 State
    """
    # 检查是否被拦截
    if state.get("IsBlocked", False):
        logger.info("Query is blocked, skipping Supervisor node.")
        return state

    # 设置 state 到 llm_service，自动记录 LLM 调用
    llm_service.set_state(state)

    try:
        # 获取当前状态
        datasets = state.get("Datasets", {})
        logger.info(f"Supervisor check: datasets={len(datasets)}")

        # 检查是否刚完成数据查询，直接路由到 summarize
        if datasets:
            latest_dataset_id = str(len(datasets))
            logger.info(f"Detected completed data query, routing to Summarize with dataset_id: {latest_dataset_id}")
            state["SummarizeDatasetId"] = latest_dataset_id
            logger.info("Supervisor node completed (direct route). Tool: summarize")
            return state

        # 初始化配置
        prompt_config = PromptConfig()
        date_func = create_date_function(state.get("CurrentDatetime", datetime.now()))
        user_query = state.get("RephraseResult", state.get("UserQuery", ""))

        system_prompt = prompt_config.render(
            "supervisor_system.j2",
            date=date_func
        )

        # 构建消息
        user_content = f"用户请求: {user_query}"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]

        # 生成工具调用
        request = LlmRequest(
            messages=messages,
            model_name=state.get("LlmModelName"),
            temperature=0.1,
        )

        response = llm_service.simple_chat(request)

        # 提取和验证工具调用
        tool_use = extract_tool_use_from_content(response)

        if tool_use is None:
            logger.warning("Failed to extract tool use")
            return state

        # 验证工具调用
        tool_use_output = SupervisorToolUseOutput(tool_use)
        is_valid, error_msg = tool_use_output.validate()
        if not is_valid:
            logger.error(f"Tool use validation failed: {error_msg}")
            return state

        # 根据工具调用路由
        tool_name = tool_use.name
        tool_args = tool_use.arguments

        if tool_name == "query_data":
            state["DataQueryTask"] = tool_args.get("task", user_query)
            state["DataQueryTable"] = tool_args.get("table", "")
            logger.info(f"Supervisor routing to DataQuery: task={state['DataQueryTask']}")

        elif tool_name == "postprocess":
            dataset_id = tool_args.get("dataset_id", "")
            task = tool_args.get("task", user_query)
            state["PostProcessTask"] = task
            state["PostProcessDatasetId"] = dataset_id
            logger.info(f"Supervisor routing to PostProcess: dataset_id={dataset_id}")

        elif tool_name == "summarize":
            dataset_id = tool_args.get("dataset_id", "")
            state["SummarizeDatasetId"] = dataset_id
            logger.info(f"Supervisor routing to Summarize: dataset_id={dataset_id}")

        else:
            logger.warning(f"Unknown tool: {tool_name}")

        logger.info(f"Supervisor node completed. Tool: {tool_name}")

    except Exception as e:
        logger.error(f"Supervisor node error: {e}")

    return state
