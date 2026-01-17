"""测试 State Graph 接口."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uuid
import datetime
from loguru import logger

from app.graph.graph import create_state_graph, app
from app.graph.core.state import State

router = APIRouter(prefix="/test", tags=["test"])


# ============== 请求/响应模型 ==============
class StateGraphRequest(BaseModel):
    """State Graph 测试请求"""
    user_query: str = Field(..., min_length=1, description="用户查询语句")
    session_id: Optional[str] = Field(None, description="会话ID，可选")
    llm_model: str = Field("glm-4.7", description="LLM 模型名称")
    llm_temperature: float = Field(0.0, description="LLM 温度设置")


class StateGraphResponse(BaseModel):
    """State Graph 测试响应"""
    session_id: str
    user_query: str
    is_blocked: bool
    block_reason: str
    understand_result: Dict[str, Any]
    response: str
    llm_calls: int
    success: bool
    execution_time: Optional[float] = None




class QueryResult(BaseModel):
    """单个查询结果"""
    query: str
    is_blocked: bool
    block_reason: str
    understand_result: Dict[str, Any]
    response: str
    success: bool
    error: Optional[str] = None


# ============== 辅助函数 ==============
def create_initial_state(
    user_query: str,
    session_id: str,
    llm_model: str = "glm-4.7",
    llm_temperature: float = 0.0
) -> State:
    """创建初始状态"""
    return {
        "SessionId": session_id,
        "SessionMessgeId": str(uuid.uuid4()),
        "UserQuery": user_query,
        "LlmModelName": llm_model,
        "LlmTemperature": llm_temperature,
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


# ============== 路由接口 ==============
@router.post("/state", response_model=StateGraphResponse)
async def test_state_graph(request: StateGraphRequest):
    """测试 State Graph 接口.

    Args:
        request: 包含所有参数的请求体

    Returns:
        执行结果
    """
    start_time = datetime.datetime.now()
    
    try:
        # 生成 session_id
        session_id = request.session_id or str(uuid.uuid4())

        logger.info(f"[Test State] Session: {session_id}, Query: {request.user_query}")

        # 初始化 State
        initial_state = create_initial_state(
            user_query=request.user_query,
            session_id=session_id,
            llm_model=request.llm_model,
            llm_temperature=request.llm_temperature
        )

        # 执行
        logger.info(f"[Test State] Invoking graph...")
        result = app.invoke(initial_state)
        
        # 计算执行时间
        execution_time = (datetime.datetime.now() - start_time).total_seconds()

        # 返回结果
        return StateGraphResponse(
            session_id=session_id,
            user_query=request.user_query,
            is_blocked=result["IsBlocked"],
            block_reason=result["BlockReason"],
            understand_result=result.get("UnderstandResult", {}),
            response=result["Response"],
            llm_calls=len(result.get("LlmCalls", [])),
            success=True,
            execution_time=execution_time
        )

    except Exception as e:
        logger.error(f"[Test State] Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "type": type(e).__name__
            }
        )


@router.get("/graph/mermaid")
async def get_graph_mermaid():
    """获取 Graph 的 Mermaid 图.

    Returns:
        Mermaid 代码
    """
    try:
        graph = create_state_graph()
        app_compiled = graph.compile()
        mermaid = app_compiled.get_graph().draw_mermaid()

        return {
            "mermaid": mermaid,
            "success": True,
        }
    except Exception as e:
        logger.error(f"[Get Mermaid] Error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "type": type(e).__name__
            }
        )


# 新增接口：测试连接
@router.get("/ping")
async def ping():
    """测试连接"""
    return {
        "status": "ok",
        "message": "pong",
        "timestamp": datetime.datetime.now().isoformat()
    }


# 新增接口：获取图信息
@router.get("/graph/info")
async def get_graph_info():
    """获取 Graph 信息"""
    try:
        graph = create_state_graph()
        app_compiled = graph.compile()
        
        return {
            "success": True,
            "nodes": list(app_compiled.get_graph().nodes.keys()) if hasattr(app_compiled.get_graph(), 'nodes') else [],
            "edges": list(app_compiled.get_graph().edges) if hasattr(app_compiled.get_graph(), 'edges') else [],
            "has_mermaid": hasattr(app_compiled.get_graph(), 'draw_mermaid')
        }
    except Exception as e:
        logger.error(f"[Get Graph Info] Error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "type": type(e).__name__
            }
        )