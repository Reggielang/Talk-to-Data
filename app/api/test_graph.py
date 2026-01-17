"""测试 State Graph 接口."""
from fastapi import APIRouter, HTTPException
import uuid
import datetime
from loguru import logger
from typing import Optional

from app.graph.graph import create_state_graph,app
from app.graph.core.state import State
from app.graph.core.model import MessageItem, LlmCallItem

router = APIRouter(prefix="/test", tags=["test"])


@router.post("/state")
async def test_state_graph(
    user_query: str,
    session_id: Optional[str] = None,
    llm_model: str = "glm-4.7",
):
    """测试 State Graph 接口.

    Args:
        user_query: 用户问题
        session_id: 会话 ID，可选
        llm_model: LLM 模型名称

    Returns:
        执行结果
    """
    try:
        # 生成 session_id
        session_id = session_id or str(uuid.uuid4())

        logger.info(f"[Test State] Session: {session_id}, Query: {user_query}")

        # 初始化 State
        initial_state: State = {
            "SessionId": session_id,
            "SessionMessgeId": str(uuid.uuid4()),
            "UserQuery": user_query,
            "LlmModelName": llm_model,
            "LlmTemperature": 0.0,
            "Messages": [],
            "SupervisorMessages": [],
            "CurrentDatetime": datetime.datetime.now(),
            "LlmCalls": [],
            "ForceEnd": False,
            "IsBlocked": False,
            "BlockReason": "",
            "UnderstandResult": {},
            "Response": "",
        }

        # 执行
        logger.info(f"[Test State] Invoking graph...")
        result = app.invoke(initial_state)

        # 返回结果
        return {
            "session_id": session_id,
            "user_query": user_query,
            "is_blocked": result["IsBlocked"],
            "block_reason": result["BlockReason"],
            "understand_result": result.get("UnderstandResult", {}),
            "response": result["Response"],
            "llm_calls": len(result.get("LlmCalls", [])),
            "success": True,
        }

    except Exception as e:
        logger.error(f"[Test State] Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/state/batch")
async def test_state_batch(
    queries: list[str],
    session_id: Optional[str] = None,
    llm_model: str = "glm-4.7",
):
    """批量测试 State Graph.

    Args:
        queries: 问题列表
        session_id: 会话 ID，可选
        llm_model: LLM 模型名称

    Returns:
        批量执行结果
    """
    try:
        session_id = session_id or str(uuid.uuid4())
        results = []

        for query in queries:
            logger.info(f"[Test Batch] Query: {query}")

            initial_state: State = {
                "SessionId": session_id,
                "SessionMessgeId": str(uuid.uuid4()),
                "UserQuery": query,
                "LlmModelName": llm_model,
                "LlmTemperature": 0.0,
                "Messages": [],
                "SupervisorMessages": [],
                "CurrentDatetime": datetime.datetime.now(),
                "LlmCalls": [],
                "ForceEnd": False,
                "IsBlocked": False,
                "BlockReason": "",
                "UnderstandResult": {},
                "Response": "",
            }

            try:
                result = app.invoke(initial_state)
                results.append({
                    "query": query,
                    "is_blocked": result["IsBlocked"],
                    "block_reason": result["BlockReason"],
                    "understand_result": result.get("UnderstandResult", {}),
                    "response": result["Response"],
                    "success": True,
                })
            except Exception as e:
                logger.error(f"[Test Batch] Query failed: {query}, Error: {e}")
                results.append({
                    "query": query,
                    "error": str(e),
                    "success": False,
                })

        return {
            "session_id": session_id,
            "total": len(queries),
            "results": results,
        }

    except Exception as e:
        logger.error(f"[Test Batch] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph/mermaid")
async def get_graph_mermaid():
    """获取 Graph 的 Mermaid 图.

    Returns:
        Mermaid 代码
    """
    try:
        graph = create_state_graph()
        app = graph.compile()
        mermaid = app.get_graph().draw_mermaid()

        return {
            "mermaid": mermaid,
            "success": True,
        }
    except Exception as e:
        logger.error(f"[Get Mermaid] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))