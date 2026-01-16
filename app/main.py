from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys

from app.api.chat import router as chat_router
from config import get_settings

settings = get_settings()

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
app.include_router(chat_router)


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
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    """启动事件."""
    logger.info("Starting TalkToData API...")


@app.on_event("shutdown")
async def shutdown_event():
    """关闭事件."""
    logger.info("Shutting down TalkToData API...")
