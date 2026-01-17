from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys
import datetime
from app.graph.graph import create_state_graph
# from app.api.chat import router as chat_router
from app.api.test_graph import router as test_router
from conf.config import settings
from typing import Optional
import uvicorn

# 简单的生命周期管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期管理器"""
    # 启动逻辑
    logger.info("Starting TalkToData API...")
    
    # 这里可以添加初始化代码
    # 例如：
    # await init_database()
    # await load_models()
    
    yield  # FastAPI 运行期
    
    # 关闭逻辑
    logger.info("Shutting down TalkToData API...")
    
    # 这里可以添加清理代码
    # 例如：
    # await close_database()
    # await unload_models()

# 配置日志
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

# 创建 FastAPI 应用
app = FastAPI(
    title="TalkToData",
    description="基于 LangGraph 的智能数据库对话查询系统",
    version="0.1.0",
    lifespan=lifespan,  # 传入生命周期管理器
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
# app.include_router(chat_router)
app.include_router(test_router)

@app.get("/")
async def root():
    """根路径."""
    return {
        "message": "TalkToData API",
        "version": "0.1.0",
        "docs": "/docs",
    }

@app.get("/health")
async def health():
    """健康检查."""
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
    }

def start_server():
    """启动服务器"""
    host = getattr(settings, "HOST", "0.0.0.0")
    port = getattr(settings, "PORT", 8000)
    reload = getattr(settings, "DEBUG", False)
    
    logger.info(f"🚀 启动服务器: {host}:{port}")
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload
    )


if __name__ == "__main__":
    start_server()