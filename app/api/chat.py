"""Chat API 路由 - 处理对话查询请求."""

import json
import uuid
import time
from datetime import datetime, timezone
from typing import Optional, Any
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from loguru import logger
from langchain_core.runnables.config import RunnableConfig


class DateTimeEncoder(json.JSONEncoder):
    """自定义 JSON 编码器，处理 datetime 对象."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def generate_short_id() -> str:
    """生成 UUID 作为 ID（去掉连字符，限制在30字符以内）."""
    return uuid.uuid4().hex[:30]

from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    SessionCreateRequest,
    SessionResponse,
    MessageResponse,
    EventResponse,
)
from app.services.graph_service import graph_service
from app.services.session_service import session_service
from app.services.persistence_service import persistence_service
from app.db.postgres import pg_client
from app.graph.graph import app
from app.graph.core.state import State
from app.graph.core.event import create_event_collector
from app.api.response_formatter import response_formatter


router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


@router.post(
    "/query",
    response_model=ChatResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def chat_query(request: ChatRequest):
    """执行查询并返回结果.

    Args:
        request: 聊天请求

    Returns:
        聊天响应

    Raises:
        HTTPException: 请求处理失败
    """
    try:
        logger.info(f"[ChatAPI] Received query: {request.query[:100]}...")

        # Debug logging: 打印接收到的历史消息
        logger.info(f"[ChatAPI] Received {len(request.messages or [])} history messages in request:")
        for i, msg in enumerate(request.messages or []):
            logger.info(f"  [{i}] role={msg.get('role')}, content={msg.get('content', '(empty)')[:50]}")

        # 生成请求ID
        request_id = generate_short_id()

        # 确保前端传入的 session_id 不超过30字符
        session_id = (request.session_id[:30] if request.session_id else None)

        # 执行查询
        final_state, event_collector = await graph_service.execute_query(
            user_query=request.query,
            session_id=session_id,
            user_email=request.user_email or "",
            model_name=request.model_name or "glm-4.6",
            save_events=True,
            messages=request.messages,
        )

        # 格式化响应（新的事件结构）
        response_data = graph_service.format_response(final_state, event_collector, request_id)

        logger.info(f"[ChatAPI] Query completed. request_id={request_id}")

        return ChatResponse(**response_data)

    except Exception as e:
        logger.error(f"[ChatAPI] Error processing query: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询处理失败: {str(e)}",
        )


@router.post(
    "/stream",
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def chat_stream(request: ChatRequest):
    """流式执行查询并返回结果.

    Args:
        request: 聊天请求

    Returns:
        流式响应

    Raises:
        HTTPException: 请求处理失败
    """
    if not request.stream:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="流式响应需要设置 stream=true",
        )

    async def event_generator():
        """生成 SSE 事件 - 实时流式发送每个节点的数据."""
        try:
            request_id = generate_short_id()
            session_id = (request.session_id[:30] if request.session_id else None) or generate_short_id()
            message_id = generate_short_id()
            model_name = request.model_name or "glm-4.6"
            user_email = request.user_email or ""

            # 发送开始事件
            yield f"event: start\ndata: {{\"type\":\"start\",\"request_id\":\"{request_id}\",\"session_id\":\"{session_id}\",\"message_id\":\"{message_id}\"}}\n\n"

            # Debug logging: 打印接收到的历史消息
            logger.info(f"[ChatAPI] Received {len(request.messages or [])} history messages in request:")
            for i, msg in enumerate(request.messages or []):
                logger.info(f"  [{i}] role={msg.get('role')}, content={msg.get('content', '(empty)')[:50]}")

            # 创建初始状态
            initial_state = State(
                SessionId=session_id,
                SessionMessgeId=message_id,
                UserQuery=request.query,
                LlmModelName=model_name,
                LlmTemperature=0.1,
                Messages=request.messages or [],  # 使用历史消息
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

            thread_id = f"{session_id}_{message_id}"
            config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
            event_collector = create_event_collector()

            # 实时执行图并流式发送每个节点的数据
            node_events = []
            for event in app.stream(initial_state, config):
                for node_name, node_state in event.items():
                    if node_name in ["__start__", "__end__"]:
                        continue

                    logger.info(f"[ChatAPI] [{node_name}] 完成")

                    # 添加事件到收集器
                    event_data = {
                        "NodeName": node_name,
                        "Type": "NODE_START",
                        "CurrentState": dict(node_state) if node_state else {},
                        "LlmCalls": list(node_state.get("LlmCalls", [])) if node_state else [],
                        "Timestamp": datetime.now(timezone.utc),
                    }
                    event_collector.events.append(event_data)
                    node_events.append(event_data)

                    # 格式化当前节点的输出
                    stage_output = response_formatter._build_stage_output(
                        node_name, node_state, [], session_id, message_id
                    )

                    # 构建节点事件数据
                    node_event = {
                        "Stage": response_formatter.NODE_NAME_MAP.get(node_name, node_name),
                        "Type": f"data-{response_formatter.NODE_NAME_MAP.get(node_name, node_name).lower()}",
                        "SessionId": session_id,
                        "SessionMessageId": message_id,
                    }
                    if stage_output:
                        node_event["StageOutput"] = stage_output

                    # 立即发送该节点的数据
                    yield f"event: node\ndata: {json.dumps(node_event, ensure_ascii=False, cls=DateTimeEncoder)}\n\n"

                    # 发送节点完成标记
                    yield f"event: finish-step\ndata: {{\"node\":\"{node_name}\"}}\n\n"

            # 获取最终状态
            final_state = app.get_state(config).values

            # 处理 Summary 节点的 text-delta 事件
            if final_state.get("SummarizeResult"):
                summary_event = {
                    "Stage": "Summary",
                    "Type": "text-delta",
                    "SessionId": session_id,
                    "SessionMessageId": message_id,
                    "Message": {
                        "Content": final_state.get("SummarizeResult"),
                        "Role": "assistant",
                        "Type": "summary",
                    },
                }
                yield f"event: node\ndata: {json.dumps(summary_event, ensure_ascii=False, cls=DateTimeEncoder)}\n\n"

            # 异步保存会话数据（不阻塞响应）
            persistence_service.save_session_data_async(
                session_id=session_id,
                session_message_id=message_id,
                user_email=user_email,
                user_query=request.query,
                final_state=final_state,
                event_collector=event_collector,
            )

            # 发送完成事件
            yield f"event: complete\ndata: {{\"request_id\":\"{request_id}\",\"session_id\":\"{session_id}\"}}\n\n"

        except Exception as e:
            logger.error(f"[ChatAPI] Error in stream: {e}")
            import traceback
            logger.error(traceback.format_exc())
            yield f"event: error\ndata: {{\"error\":\"{str(e)}\"}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post(
    "/sessions",
    response_model=SessionResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def create_session(request: SessionCreateRequest):
    """创建新会话.

    Args:
        request: 创建会话请求

    Returns:
        会话响应

    Raises:
        HTTPException: 创建失败
    """
    try:
        session_id = pg_client.create_session(
            user_sid=request.user_sid,
            user_email=request.user_email,
            note=request.note,
        )

        # 获取创建的会话信息
        session_data = pg_client.get_session(session_id)

        logger.info(f"[ChatAPI] Created session: {session_id}")

        return SessionResponse(**session_data)

    except Exception as e:
        logger.error(f"[ChatAPI] Error creating session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建会话失败: {str(e)}",
        )


@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_session(session_id: str):
    """获取会话信息.

    Args:
        session_id: 会话ID

    Returns:
        会话响应

    Raises:
        HTTPException: 会话不存在
    """
    try:
        session_data = pg_client.get_session(session_id)

        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会话不存在: {session_id}",
            )

        return SessionResponse(**session_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ChatAPI] Error getting session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取会话失败: {str(e)}",
        )


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[MessageResponse],
    responses={500: {"model": ErrorResponse}},
)
async def get_session_messages(
    session_id: str,
    limit: int = 100,
):
    """获取会话消息历史.

    Args:
        session_id: 会话ID
        limit: 返回条数限制

    Returns:
        消息列表

    Raises:
        HTTPException: 获取失败
    """
    try:
        messages = await session_service.get_session_history(session_id, limit)

        return [MessageResponse(**msg) for msg in messages]

    except Exception as e:
        logger.error(f"[ChatAPI] Error getting messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取消息历史失败: {str(e)}",
        )


@router.get(
    "/sessions/{session_id}/events",
    response_model=list[EventResponse],
    responses={500: {"model": ErrorResponse}},
)
async def get_session_events(
    session_id: str,
    message_id: Optional[str] = None,
):
    """获取会话事件.

    Args:
        session_id: 会话ID
        message_id: 消息ID（可选）

    Returns:
        事件列表

    Raises:
        HTTPException: 获取失败
    """
    try:
        events = await session_service.get_session_events(session_id, message_id)

        return [EventResponse(**_format_event(e)) for e in events]

    except Exception as e:
        logger.error(f"[ChatAPI] Error getting events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取事件失败: {str(e)}",
        )


def _format_event(event: dict) -> dict:
    """格式化事件数据."""
    event_body = event.get("event_body", {})
    if isinstance(event_body, str):
        try:
            event_body = json.loads(event_body)
        except:
            pass

    return {
        "id": event.get("id", ""),
        "session_id": event.get("session_id", ""),
        "session_message_id": event.get("session_message_id", ""),
        "node_name": event_body.get("NodeName", ""),
        "event_type": event_body.get("Type", ""),
        "event_body": event_body,
        "created_at": event.get("created_at", datetime.now()),
        "has_error": event.get("has_error", False),
        "duration_ms": event.get("duration_ms", 0),
    }
