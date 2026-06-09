"""SQLAlchemy 基础配置 - 数据库连接和会话管理."""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.conf.config import settings


# 创建异步引擎
async_engine = create_async_engine(
    f"postgresql+asyncpg://{settings.pg_user}:{settings.pg_password}@"
    f"{settings.pg_host}:{settings.pg_port}/{settings.pg_database}",
    echo=False,  # 生产环境设为 False
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# 创建异步会话工厂
async_session_factory = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """所有 SQLAlchemy Model 的基类."""
    pass
