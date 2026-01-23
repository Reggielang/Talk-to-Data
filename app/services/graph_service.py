"""图执行服务 - 封装 LangGraph 的执行逻辑."""

import uuid
from datetime import datetime, timezone
from typing import Optional
from langchain_core.runnables.config import RunnableConfig
from loguru import logger

from app.graph.graph import create_state_graph, app
from app.graph.core.state import State
from app.graph.core.event import EventCollector, create_event_collector
from app.api.response_formatter import response_formatter
from app.services.persistence_service import persistence_service


class GraphService:
    """图执行服务 - 负责执行 LangGraph 并管理会话."""

    def __init__(self):
        """初始化图服务."""
        self.app = app
        self.formatter = response_formatter

    async def execute_query(
        self,
        user_query: str,
        session_id: Optional[str] = None,
        session_message_id: Optional[str] = None,
        user_email: str = "",
        model_name: str = "glm-4.6",
        save_events: bool = True,
        messages: list = None,
    ) -> tuple[dict, EventCollector]:
        """执行查询并返回结果.

        Args:
            user_query: 用户查询
            session_id: 会话ID，如果为空则创建新会话
            session_message_id: 会话消息ID
            user_email: 用户邮箱
            model_name: LLM 模型名称
            save_events: 是否保存事件到 PG
            messages: 历史消息列表

        Returns:
            (最终状态, 事件收集器)
        """
        # 1. 创建或获取会话
        if not session_id:
            session_id = uuid.uuid4().hex[:30]
            logger.info(f"Created new session_id: {session_id}")

        # 2. 创建消息ID
        if not session_message_id:
            session_message_id = uuid.uuid4().hex[:30]

        # 3. 创建初始状态
        initial_state = State(
            SessionId=session_id,
            SessionMessgeId=session_message_id,
            UserQuery=user_query,
            LlmModelName=model_name,
            LlmTemperature=0.1,
            Messages=messages or [],  # 使用传入的历史消息
            CurrentDatetime=datetime.now(),
            LlmCalls=[],
            ForceEnd=False,
            IsBlocked=False,
            BlockReason="",
            RephraseResult="",
            UnderstandResult={},
            DataQueryTask="",
            DataQueryTable="",
            SqlGenResult={},
            DataQueryResult={},
            PostProcessTask="",
            PostProcessDatasetId="",
            PostProcessResult={},
            SummarizeDatasetId="",
            SummarizeResult="",
            Datasets={},
            DataQueryRethinkTimes=0,
            PostprocessRethinkTimes=0,
        )

        logger.info(f"[GraphService] Initial state Messages count: {len(initial_state.get('Messages', []))}")
        for i, msg in enumerate(initial_state.get('Messages', [])):
            logger.info(f"  [{i}] role={msg.get('role')}, content={msg.get('content', '(empty)')[:50]}")

        # 4. 创建配置
        thread_id = f"{session_id}_{session_message_id}"
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

        # 5. 创建事件收集器
        event_collector = create_event_collector()

        # 6. 执行图并收集事件
        logger.info(f"[GraphService] Executing query: {user_query[:100]}...")
        logger.info(f"[GraphService] session_id={session_id}, message_id={session_message_id}")

        try:
            for event in self.app.stream(initial_state, config):
                for node_name, node_state in event.items():
                    if node_name in ["__start__", "__end__"]:
                        event_collector.events.append({
                            "NodeName": node_name,
                            "Type": "NODE_START",
                            "CurrentState": dict(node_state) if node_state else {},
                            "LlmCalls": [],
                            "Timestamp": datetime.now(timezone.utc),
                        })
                        continue

                    logger.info(f"[GraphService] [{node_name}] 完成")

                    # Debug: 打印节点执行后的 Messages 状态
                    node_messages = node_state.get("Messages", []) if node_state else []
                    logger.info(f"[GraphService] After {node_name}, Messages count: {len(node_messages)}")
                    for i, msg in enumerate(node_messages):
                        logger.info(f"  [{i}] role={msg.get('role')}, content={msg.get('content', '(empty)')[:50]}")

                    event_collector.events.append({
                        "NodeName": node_name,
                        "Type": "NODE_START",
                        "CurrentState": dict(node_state) if node_state else {},
                        "LlmCalls": list(node_state.get("LlmCalls", [])) if node_state else [],
                        "Timestamp": datetime.now(timezone.utc),
                    })

                    event_collector.events.append({
                        "NodeName": node_name,
                        "Type": "NODE_END",
                        "CurrentState": dict(node_state) if node_state else {},
                        "LlmCalls": [],
                        "Timestamp": datetime.now(timezone.utc),
                    })

            final_state = self.app.get_state(config).values

            # 7. 保存会话数据到数据库
            if save_events:
                persistence_service.save_session_data_async(
                    session_id=session_id,
                    session_message_id=session_message_id,
                    user_email=user_email,
                    user_query=user_query,
                    final_state=final_state,
                    event_collector=event_collector,
                )

        except Exception as e:
            logger.error(f"[GraphService] Error executing query: {e}")
            raise

        return final_state, event_collector

    def format_response(self, state: dict, event_collector: EventCollector, request_id: str) -> dict:
        """格式化响应数据 - 使用 ResponseFormatter.

        Args:
            state: 最终状态
            event_collector: 事件收集器
            request_id: 请求ID

        Returns:
            格式化的响应字典
        """
        return self.formatter.format_response(state, event_collector, request_id)


# 全局单例
graph_service = GraphService()