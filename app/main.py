"""TalkToData FastAPI 应用主入口."""

import asyncio
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
import datetime
import uvicorn
import time
from sqlalchemy import text

from app.api.chat import router as chat_router
from app.conf.config import settings
from app.db.mysql import mysql_client
from app.db.base import async_session_factory


async def check_mysql_connection() -> bool:
    """检查 MySQL 连接."""
    try:
        result = mysql_client.execute_query("SELECT 1 as ping")
        if result and result[0].get("ping") == 1:
            logger.info(f"✅ MySQL 连接成功: {settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ MySQL 连接失败: {e}")
        logger.error(f"   配置: host={settings.mysql_host}, port={settings.mysql_port}, database={settings.mysql_database}")
        return False


async def check_postgres_connection() -> bool:
    """检查 PostgreSQL 异步连接（SQLAlchemy）."""
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
            logger.info(f"✅ PostgreSQL 连接成功: {settings.pg_host}:{settings.pg_port}/{settings.pg_database}")
            return True
    except Exception as e:
        logger.error(f"❌ PostgreSQL 连接失败: {e}")
        logger.error(f"   配置: host={settings.pg_host}, port={settings.pg_port}, database={settings.pg_database}")
        return False


async def startup_health_check():
    """启动时健康检查 - 所有服务必须可用."""
    logger.info("=" * 60)
    logger.info("🔍 开始启动时健康检查...")
    logger.info("=" * 60)

    checks = {
        "MySQL": check_mysql_connection(),
        "PostgreSQL": check_postgres_connection(),
    }

    results = {}
    for name, coro in checks.items():
        try:
            results[name] = await coro
        except Exception as e:
            logger.error(f"❌ {name} 检查异常: {e}")
            results[name] = False

    logger.info("=" * 60)

    # 检查结果
    all_passed = all(results.values())

    if all_passed:
        logger.info("🎉 所有服务连接检查通过！")
        logger.info("=" * 60)
    else:
        failed_services = [name for name, passed in results.items() if not passed]
        logger.error(f"❌ 以下服务连接失败: {', '.join(failed_services)}")
        logger.error("=" * 60)
        logger.error("")
        logger.error("🚨 项目无法启动！请检查:")
        logger.error("   1. 数据库服务是否运行")
        logger.error("   2. .env 配置是否正确")
        logger.error("   3. 网络连接是否正常")
        logger.error("")
        raise RuntimeError(f"服务连接失败: {', '.join(failed_services)}")

    return all_passed


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期管理器"""
    # 启动逻辑
    logger.info("Starting TalkToData API...")

    # 健康检查 - 失败则阻止启动
    await startup_health_check()

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


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有 HTTP 请求和响应."""
    start_time = time.time()

    # 记录请求
    logger.info(f"📥 {request.method} {request.url.path}")

    # 处理请求
    response = await call_next(request)

    # 记录响应
    process_time = time.time() - start_time
    logger.info(f"📤 {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.3f}s")

    return response


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
