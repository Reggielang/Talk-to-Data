"""数据库会话管理 - 提供依赖注入和上下文管理器."""

from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import async_session_factory
from loguru import logger


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话 (用于 FastAPI 依赖注入).

    Yields:
        AsyncSession: 数据库会话
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
