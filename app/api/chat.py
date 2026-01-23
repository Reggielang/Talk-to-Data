"""Chat API 路由 - 处理对话查询请求."""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from loguru import logger

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
from app.db.postgres import pg_client


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

        # 生成请求ID
        request_id = uuid.uuid4().hex[:20]

        # 执行查询
        final_state, event_collector = await graph_service.execute_query(
            user_query=request.query,
            session_id=request.session_id,
            user_email=request.user_email or "",
            model_name=request.model_name or "glm-4.6",
            save_events=True,
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
        """生成 SSE 事件."""
        try:
            request_id = uuid.uuid4().hex[:20]
            session_id = request.session_id or uuid.uuid4().hex[:30]
            message_id = uuid.uuid4().hex[:30]

            # 发送开始事件
            yield f"event: start\ndata: {{\"type\":\"start\",\"request_id\":\"{request_id}\",\"session_id\":\"{session_id}\",\"message_id\":\"{message_id}\"}}\n\n"

            # 执行查询
            final_state, event_collector = await graph_service.execute_query(
                user_query=request.query,
                session_id=session_id,
                session_message_id=message_id,
                user_email=request.user_email or "",
                model_name=request.model_name or "glm-4.6",
                save_events=True,
            )

            # 发送进度事件（每个节点）
            events = event_collector.get_events()
            for event in events:
                node_name = event.get("NodeName", "")
                event_type = event.get("Type", "")
                if node_name and event_type:
                    yield f"event: progress\ndata: {{\"node\":\"{node_name}\",\"type\":\"{event_type}\"}}\n\n"

            # 格式化最终结果（新的事件结构）
            response_data = graph_service.format_response(final_state, event_collector, request_id)

            # 发送完成事件
            yield f"event: complete\ndata: {json.dumps(response_data, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"[ChatAPI] Error in stream: {e}")
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
