"""Chat API 路由 - 处理对话查询请求."""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from loguru import logger


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
from app.api.response_formatter import response_formatter


router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


# ==================== 查询相关 ====================

@router.post(
    "/query",
    response_model=ChatResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def chat_query(request: ChatRequest):
    """执行查询并返回结果（非流式）."""
    try:
        logger.info(f"[ChatAPI] Query: {request.query[:100]}...")

        request_id = generate_short_id()
        session_id = (request.session_id[:30] if request.session_id else None)

        final_state, event_collector = await graph_service.execute_query(
            user_query=request.query,
            session_id=session_id,
            user_email=request.user_email or "",
            model_name=request.model_name or "glm-4.6",
            save_events=True,
            messages=request.messages,
        )

        response_data = response_formatter.format_response(final_state, event_collector, request_id)
        logger.info(f"[ChatAPI] Query completed. request_id={request_id}")

        return ChatResponse(**response_data)

    except Exception as e:
        logger.error(f"[ChatAPI] Query error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询处理失败: {str(e)}",
        )


@router.post(
    "/stream",
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def chat_stream(request: ChatRequest):
    """流式执行查询并返回结果（异步）."""
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

            # 发送开始事件
            yield f"event: start\ndata: {{\"type\":\"start\",\"request_id\":\"{request_id}\",\"session_id\":\"{session_id}\",\"message_id\":\"{message_id}\"}}\n\n"

            logger.info(f"[ChatAPI] Stream query: {request.query[:100]}...")

            final_state = None

            # 异步流式执行图
            async for event_data in graph_service.stream_query(
                user_query=request.query,
                session_id=session_id,
                session_message_id=message_id,
                model_name=model_name,
                messages=request.messages or [],
            ):
                if event_data.get("__final__"):
                    final_state = event_data["final_state"]
                    break

                node_name = event_data["node_name"]
                node_state = event_data["node_state"]

                if node_name in ["__start__", "__end__"]:
                    continue

                logger.info(f"[ChatAPI] [{node_name}] 完成")

                # 构建节点输出
                stage_output = response_formatter._build_stage_output(
                    node_name, node_state, [], session_id, message_id
                )

                stage_name = response_formatter.NODE_NAME_MAP.get(node_name, node_name) or node_name
                node_event = {
                    "Stage": stage_name,
                    "Type": f"data-{str(stage_name).lower()}",
                    "SessionId": session_id,
                    "SessionMessageId": message_id,
                }
                if stage_output:
                    node_event["StageOutput"] = stage_output

                # 发送节点事件
                yield f"event: node\ndata: {json.dumps(node_event, ensure_ascii=False, cls=DateTimeEncoder)}\n\n"
                yield f"event: finish-step\ndata: {{\"node\":\"{node_name}\"}}\n\n"

            # 发送 Summary 最终输出
            if final_state and final_state.get("SummarizeResult"):
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

            # 发送完成事件
            yield f"event: complete\ndata: {{\"request_id\":\"{request_id}\",\"session_id\":\"{session_id}\"}}\n\n"

        except Exception as e:
            logger.error(f"[ChatAPI] Stream error: {e}")
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


# ==================== 会话相关 ====================

@router.post(
    "/sessions",
    response_model=SessionResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def create_session(request: SessionCreateRequest):
    """创建新会话."""
    try:
        session_id = uuid.uuid4().hex[:30]

        await session_service.create_session(
            session_id=session_id,
            user_email=request.user_email,
            note=request.note,
        )

        session = await session_service.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="创建会话失败",
            )

        logger.info(f"[ChatAPI] Created session: {session_id}")
        return _session_to_response(session)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ChatAPI] Create session error: {e}")
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
    """获取会话信息."""
    try:
        session = await session_service.get_session(session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会话不存在: {session_id}",
            )

        return _session_to_response(session)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ChatAPI] Get session error: {e}")
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
    """获取会话消息历史."""
    try:
        messages = await session_service.get_session_history(session_id, limit)
        return [MessageResponse(**msg) for msg in messages]

    except Exception as e:
        logger.error(f"[ChatAPI] Get messages error: {e}")
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
    """获取会话事件."""
    try:
        events = await session_service.get_session_events(session_id, message_id)
        return [EventResponse(**_format_event(e)) for e in events]

    except Exception as e:
        logger.error(f"[ChatAPI] Get events error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取事件失败: {str(e)}",
        )


# ==================== 工具函数 ====================

def _session_to_response(session_model) -> dict:
    """将 SessionModel 转换为 SessionResponse 格式的字典."""
    return {
        "session_id": session_model.id,
        "user_sid": session_model.user_sid,
        "user_email": session_model.user_email,
        "note": session_model.note,
        "created_at": session_model.created_at,
        "updated_at": session_model.updated_at,
        "expired_at": session_model.expired_at,
    }


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
