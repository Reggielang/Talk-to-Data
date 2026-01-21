"""API 响应格式化器 - 将 Graph 执行结果转换为 API 响应格式."""

import re
import json
from typing import Optional
from loguru import logger

from app.graph.core.event import EventCollector


class ResponseFormatter:
    """响应格式化器 - 负责将内部状态转换为 API 响应格式."""

    # 节点名称映射（内部名称 -> API 输出名称）
    NODE_NAME_MAP = {
        "BLOCK": "Block",
        "UNDERSTAND": "Understand",
        "SUPERVISOR": "Supervisor",
        "DATA_QUERY": "DataQuery",
        "POSTPROCESS": "PostProcess",
        "SUMMARIZE": "Summary",
        "__start__": "__start__",
        "__end__": "__end__",
    }

    @classmethod
    def format_response(
        cls,
        state: dict,
        event_collector: EventCollector,
        request_id: str,
    ) -> dict:
        """格式化响应数据.

        Args:
            state: 最终状态
            event_collector: 事件收集器
            request_id: 请求ID

        Returns:
            格式化的响应字典
        """
        session_id = state.get("SessionId", "")
        session_message_id = state.get("SessionMessgeId", "")

        events = cls._format_events(
            event_collector.get_events(),
            session_id,
            session_message_id,
        )

        return {
            "Meta": {"RequestId": request_id},
            "Data": {
                "SessionId": session_id,
                "SessionMessageId": session_message_id,
                "Events": events,
            },
        }

    @classmethod
    def _format_events(
        cls,
        raw_events: list[dict],
        session_id: str,
        session_message_id: str,
    ) -> list[dict]:
        """格式化事件列表.

        Args:
            raw_events: 原始事件列表
            session_id: 会话ID
            session_message_id: 消息ID

        Returns:
            格式化后的事件列表
        """
        events = []

        for event in raw_events:
            node_name = event.get("NodeName", "")
            event_type = event.get("Type", "")
            current_state = event.get("CurrentState", {})

            # 跳过 NODE_END 事件，只处理 NODE_START
            if event_type == "NODE_END":
                continue

            # 跳过 __start__ 和 __end__ 的数据事件（它们会在最后手动添加）
            if node_name in ["__start__", "__end__"]:
                continue

            # 添加数据事件
            event_item = {
                "Stage": cls.NODE_NAME_MAP.get(node_name, node_name),
                "Type": f"data-{cls.NODE_NAME_MAP.get(node_name, node_name).lower()}",
                "SessionId": session_id,
                "SessionMessageId": session_message_id,
            }

            # 添加 StageOutput
            stage_output = cls._build_stage_output(node_name, current_state, events, session_id, session_message_id)
            if stage_output:
                event_item["StageOutput"] = stage_output

            events.append(event_item)

            # 添加 finish-step 事件
            events.append({
                "Stage": cls.NODE_NAME_MAP.get(node_name, node_name),
                "Type": "finish-step",
                "SessionId": session_id,
                "SessionMessageId": session_message_id,
            })

        # 添加 __end__ 事件
        events.append({
            "Stage": "__end__",
            "Type": "data-__end__",
            "SessionId": session_id,
            "SessionMessageId": session_message_id,
            "StageOutput": {"QuestionVerifiedType": "none"},
        })
        events.append({
            "Stage": "__end__",
            "Type": "finish",
            "SessionId": session_id,
            "SessionMessageId": session_message_id,
        })

        return events

    @classmethod
    def _build_stage_output(
        cls,
        node_name: str,
        current_state: dict,
        events: list,
        session_id: str,
        session_message_id: str,
    ) -> Optional[dict]:
        """构建节点输出.

        Args:
            node_name: 节点名称
            current_state: 当前状态
            events: 事件列表（用于添加额外事件）
            session_id: 会话ID
            session_message_id: 消息ID

        Returns:
            StageOutput 字典，如果不需要输出则返回 None
        """
        if node_name == "BLOCK":
            return cls._format_block_output(current_state)

        elif node_name == "UNDERSTAND":
            return cls._format_understand_output(current_state)

        elif node_name == "SUPERVISOR":
            return cls._format_supervisor_output(current_state)

        elif node_name == "DATA_QUERY":
            return cls._format_data_query_output(current_state)

        elif node_name == "POSTPROCESS":
            return cls._format_postprocess_output(current_state)

        elif node_name == "SUMMARIZE":
            cls._add_summary_text_delta_event(current_state, events, session_id, session_message_id)
            return None  # Summary 不需要 StageOutput

        return None

    @classmethod
    def _format_block_output(cls, state: dict) -> Optional[dict]:
        """格式化 Block 节点输出."""
        if not state.get("IsBlocked"):
            return None
        return {
            "Blocked": True,
            "BlockReason": state.get("BlockReason", ""),
        }

    @classmethod
    def _format_understand_output(cls, state: dict) -> dict:
        """格式化 Understand 节点输出."""
        output = {}
        if state.get("RephraseResult"):
            output["RephrasedUserQuery"] = state.get("RephraseResult")
        if state.get("UnderstandResult"):
            output.update(state.get("UnderstandResult", {}))
        return output or None

    @classmethod
    def _format_supervisor_output(cls, state: dict) -> Optional[dict]:
        """格式化 Supervisor 节点输出."""
        # 从 UnderstandResult 中获取工具调用信息
        understand_result = state.get("UnderstandResult", {})
        if understand_result.get("tool"):
            return {
                "SupervisorToolCalls": [{
                    "Name": understand_result.get("tool", ""),
                    "Arguments": understand_result.get("tool_arguments", "{}")
                }]
            }
        return None

    @classmethod
    def _format_data_query_output(cls, state: dict) -> Optional[dict]:
        """格式化 DataQuery 节点输出."""
        output = {}

        if state.get("SqlGenResult"):
            output["GeneratedSql"] = state.get("SqlGenResult", {}).get("Sql", "")

        if state.get("DataQueryResult"):
            data_result = state.get("DataQueryResult", {})
            output["DataQueryResult"] = {
                "AffectRows": data_result.get("DataRowLength", 0),
                "JsonContent": data_result.get("Content", "[]"),
                "JsonContentRows": data_result.get("DataRowLength", 0),
            }

        return output or None

    @classmethod
    def _format_postprocess_output(cls, state: dict) -> Optional[dict]:
        """格式化 PostProcess 节点输出."""
        result = state.get("PostProcessResult")
        if result:
            return {"PostProcessResult": result}
        return None

    @classmethod
    def _add_summary_text_delta_event(
        cls,
        state: dict,
        events: list,
        session_id: str,
        session_message_id: str,
    ) -> None:
        """添加 Summary 的 text-delta 事件."""
        # 使用 SummarizeResult 作为总结内容
        summary_result = state.get("SummarizeResult", "")
        if not summary_result:
            return

        # 查找最后一个 LLM 调用获取时间和 ID
        #（SUMMARIZE 节点的 LLM 调用通常是最后一次）
        llm_calls = state.get("LlmCalls", [])
        call_id = ""
        first_token_at = ""
        if llm_calls:
            last_call = llm_calls[-1]
            call_id = last_call.get("Id", "")
            first_token_at = last_call.get("StartAt", "")

        events.append({
            "Stage": "Summary",
            "Type": "text-delta",
            "SessionId": session_id,
            "SessionMessageId": session_message_id,
            "Message": {
                "Id": call_id,
                "Content": summary_result,
                "Role": "assistant",
                "Type": "summary",
                "FirstTokenAt": first_token_at,
            },
        })

    @classmethod
    def _extract_tool_calls(cls, content: str) -> list[dict]:
        """从 LLM 返回内容中提取工具调用.

        Args:
            content: LLM 返回的内容

        Returns:
            工具调用列表 [{"Name": "...", "Arguments": "{...}"}]
        """
        tool_calls = []

        # 尝试提取 JSON 格式的工具调用
        pattern = r'\{"tool_use":\s*\{"name":\s*"([^"]+)",\s*"arguments":\s*(\{.*?\})\}\}'
        matches = re.findall(pattern, content, re.DOTALL)

        for name, args in matches:
            try:
                # 验证并重新序列化 JSON
                parsed_args = json.loads(args)
                tool_calls.append({
                    "Name": name,
                    "Arguments": json.dumps(parsed_args, ensure_ascii=False)
                })
            except json.JSONDecodeError:
                # 如果解析失败，直接使用原始字符串
                tool_calls.append({
                    "Name": name,
                    "Arguments": args
                })

        return tool_calls


# 全局单例
response_formatter = ResponseFormatter()
