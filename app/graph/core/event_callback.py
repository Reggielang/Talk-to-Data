"""LangGraph 事件回调处理器 - 自动记录节点执行事件

参考 Go 版本的事件机制，通过 LangGraph 的回调系统实现事件自动收集，
节点代码无需关心事件记录，保持解耦。
"""

from typing import Any, Dict, Optional
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from loguru import logger
import datetime

from app.graph.core.event import EventCollector, EventType, Event


class EventCollectorCallback(BaseCallbackHandler):
    """LangGraph 回调处理器 - 自动收集执行事件

    通过 LangGraph 的回调机制，在节点执行前后自动记录事件，
    无需修改节点代码。
    """

    def __init__(self, event_collector: EventCollector):
        """初始化回调处理器

        Args:
            event_collector: 事件收集器实例
        """
        super().__init__()
        self.event_collector = event_collector
        self._node_stack: list[str] = []  # 节点调用栈
        self._node_states: dict[str, dict] = {}  # 节点状态快照

    # LangGraph 节点生命周期回调

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """链/节点开始执行时的回调"""
        # 尝试从 metadata 或 serialized 中获取节点名称
        node_name = self._extract_node_name(serialized, metadata)

        if node_name and node_name not in ["__start__", "__end__"]:
            self._node_stack.append(node_name)

            # 记录节点开始事件
            state_snapshot = self._extract_state_from_inputs(inputs)
            self._node_states[node_name] = {
                "before": state_snapshot,
                "llm_calls_before": state_snapshot.get("LlmCalls", []).copy() if isinstance(state_snapshot.get("LlmCalls"), list) else [],
            }

            # 创建开始事件
            event = Event(
                NodeName=node_name,
                Type=EventType.START,
                StageOutput=None,
                Message=None,
                Error=None,
                CurrentState=state_snapshot,
                LlmCalls=[],  # 开始时没有新的 LLM 调用
                Timestamp=datetime.datetime.now(),
            )
            self.event_collector.events.append(event)

            logger.debug(f"[Callback] Node start: {node_name}")

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """链/节点结束执行时的回调"""
        if not self._node_stack:
            return

        node_name = self._node_stack.pop()

        if node_name in self._node_states:
            # 获取节点执行前的状态
            node_state_info = self._node_states.pop(node_name)
            state_after = self._extract_state_from_inputs(outputs)

            # 计算新增的 LLM 调用
            llm_calls_before = node_state_info.get("llm_calls_before", [])
            llm_calls_after = state_after.get("LlmCalls", [])
            new_llm_calls = llm_calls_after[len(llm_calls_before):] if isinstance(llm_calls_after, list) else []

            # 创建结束事件
            event = Event(
                NodeName=node_name,
                Type=EventType.END,
                StageOutput=None,
                Message=None,
                Error=None,
                CurrentState=state_after,
                LlmCalls=new_llm_calls,  # 只包含新增的 LLM 调用
                Timestamp=datetime.datetime.now(),
            )
            self.event_collector.events.append(event)

            logger.debug(f"[Callback] Node end: {node_name}, new llm_calls: {len(new_llm_calls)}")

    def on_chain_error(
        self,
        error: Exception,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """链/节点执行出错时的回调"""
        if not self._node_stack:
            return

        node_name = self._node_stack.pop()

        if node_name in self._node_states:
            node_state_info = self._node_states.pop(node_name)
            state_before = node_state_info.get("before", {})

            # 创建错误事件
            event = Event(
                NodeName=node_name,
                Type=EventType.ERROR,
                StageOutput=None,
                Message=None,
                Error=str(error),
                CurrentState=state_before,
                LlmCalls=[],
                Timestamp=datetime.datetime.now(),
            )
            self.event_collector.events.append(event)

            logger.error(f"[Callback] Node error: {node_name} - {error}")

    # LLM 调用相关回调

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: list[str],
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """LLM 开始调用时的回调"""
        current_node = self._node_stack[-1] if self._node_stack else None
        if current_node:
            logger.debug(f"[Callback] LLM start in node: {current_node}")

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """LLM 调用结束时的回调"""
        current_node = self._node_stack[-1] if self._node_stack else None
        if current_node:
            logger.debug(f"[Callback] LLM end in node: {current_node}")

    # 辅助方法

    def _extract_node_name(
        self,
        serialized: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """从序列化数据或元数据中提取节点名称"""
        # 尝试从 metadata 获取
        if metadata:
            if "langgraph_node" in metadata:
                return metadata["langgraph_node"]
            if "__event_name" in metadata:
                return metadata["__event_name"]

        # 尝试从 serialized 获取
        if "id" in serialized:
            id_list = serialized["id"]
            if isinstance(id_list, list) and len(id_list) > 0:
                return id_list[-1]

        return None

    def _extract_state_from_inputs(self, inputs: Any) -> Dict[str, Any]:
        """从输入中提取状态"""
        if isinstance(inputs, dict):
            # 检查是否已经是 State 格式
            if "LlmCalls" in inputs or "Messages" in inputs:
                return dict(inputs)
            # 检查是否嵌套在 "messages" 或其他键下
            for key, value in inputs.items():
                if isinstance(value, dict) and "LlmCalls" in value:
                    return dict(value)
        return {}
