"""TalkToData FastAPI 应用主入口."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
import sys
import datetime
import uvicorn

from app.api.chat import router as chat_router
from app.conf.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期管理器"""
    # 启动逻辑
    logger.info("Starting TalkToData API...")

    # 这里可以添加初始化代码
    # 例如：
    # await init_database()
    # await load_models()

    yield

    # 关闭逻辑
    logger.info("Shutting down TalkToData API...")


def custom_logger():
    """配置自定义日志."""
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
    )
    logger.add(
        "logs/app.log",
        rotation="500 MB",
        retention="10 days",
        level="DEBUG",
    )


# 配置日志
custom_logger()


# 创建 FastAPI 应用
app = FastAPI(
    title="TalkToData",
    description="基于 LangGraph 的智能数据库对话查询系统",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc),
            "timestamp": datetime.datetime.now().isoformat(),
        }
    )


# 注册路由
app.include_router(chat_router)


@app.get("/", tags=["root"])
async def root():
    """根路径."""
    return {
        "message": "TalkToData API",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "POST /chat/query": "执行查询（非流式）",
            "POST /chat/stream": "执行查询（流式 SSE）",
            "POST /chat/sessions": "创建会话",
            "GET /chat/sessions/{session_id}": "获取会话信息",
            "GET /chat/sessions/{session_id}/messages": "获取会话消息",
            "GET /chat/sessions/{session_id}/events": "获取会话事件",
            "GET /health": "健康检查",
        }
    }


@app.get("/health", tags=["health"])
async def health():
    """健康检查."""
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "version": "0.1.0",
    }


def start_server():
    """启动服务器."""
    host = settings.api_host
    port = settings.api_port

    logger.info(f"🚀 启动服务器: {host}:{port}")
    logger.info(f"📚 API 文档: http://{host}:{port}/docs")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    start_server()
