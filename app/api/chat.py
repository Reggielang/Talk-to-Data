from fastapi import APIRouter, HTTPException
import uuid
from loguru import logger

from app.models import ChatRequest, ChatResponse
from app.graph.conversation import conversation_graph

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """聊天接口."""
    try:
        # 生成或使用现有 session_id
        session_id = request.session_id or str(uuid.uuid4())

        logger.info(f"Session {session_id}: {request.message}")

        # 初始化状态
        initial_state = {
            "messages": [],
            "session_id": session_id,
            "user_query": request.message,
            "generated_sql": "",
            "query_result": [],
            "error": "",
            "response": "",
        }

        # 执行对话图
        result = conversation_graph.invoke(initial_state)

        return ChatResponse(
            response=result["response"],
            sql=result.get("generated_sql"),
            data=result.get("query_result") or None,
            session_id=session_id,
        )

    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{session_id}")
async def get_history(session_id: str, limit: int = 10):
    """获取对话历史."""
    from app.db.postgres import pg_client

    try:
        history = pg_client.get_query_history(session_id, limit)
        return {"session_id": session_id, "history": history}
    except Exception as e:
        logger.error(f"Get history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """清除会话."""
    from app.db.redis import redis_client

    try:
        redis_client.clear_session(session_id)
        return {"message": "Session cleared", "session_id": session_id}
    except Exception as e:
        logger.error(f"Clear session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
