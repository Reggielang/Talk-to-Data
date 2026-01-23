"""会话管理服务 - 负责会话和消息的查询管理."""

from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.models import SessionModel, SessionMessageModel, SessionEventModel
from app.db.base import async_session_factory


class SessionService:
    """会话管理服务 - 负责会话相关的 CRUD 操作."""

    async def get_session(self, session_id: str) -> Optional[SessionModel]:
        """获取会话信息.

        Args:
            session_id: 会话ID

        Returns:
            SessionModel 对象，不存在则返回 None
        """
        try:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(SessionModel).where(SessionModel.id == session_id)
                )
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"[SessionService] Error getting session: {e}")
            return None

    async def create_session(
        self,
        session_id: str,
        user_email: str,
        note: Optional[str] = None,
        expired_days: int = 7,
    ) -> str:
        """创建新会话.

        Args:
            session_id: 会话ID
            user_email: 用户邮箱
            note: 备注
            expired_days: 过期天数

        Returns:
            会话ID
        """
        try:
            async with async_session_factory() as session:
                now = datetime.now(timezone.utc)
                expired_at = now + timedelta(days=expired_days)

                session_model = SessionModel(
                    id=session_id,
                    user_sid=session_id,
                    user_email=user_email,
                    note=note,
                    created_at=now,
                    updated_at=now,
                    expired_at=expired_at,
                )
                session.add(session_model)
                await session.commit()
                await session.refresh(session_model)
                return session_model.id
        except Exception as e:
            logger.error(f"[SessionService] Error creating session: {e}")
            raise

    async def ensure_session_exists(
        self,
        session_id: str,
        user_email: str,
    ) -> None:
        """确保会话存在，如果不存在则创建.

        Args:
            session_id: 会话ID
            user_email: 用户邮箱
        """
        try:
            # 先检查是否存在
            existing = await self.get_session(session_id)
            if existing:
                # 更新 updated_at
                async with async_session_factory() as session:
                    result = await session.execute(
                        select(SessionModel).where(SessionModel.id == session_id)
                    )
                    session_model = result.scalar_one_or_none()
                    if session_model:
                        session_model.updated_at = datetime.now(timezone.utc)
                        await session.commit()
            else:
                # 创建新会话
                await self.create_session(session_id, user_email)
        except Exception as e:
            logger.error(f"[SessionService] Error ensuring session exists: {e}")
            raise

    async def get_session_history(self, session_id: str, limit: int = 100) -> list[dict]:
        """获取会话消息历史.

        Args:
            session_id: 会话ID
            limit: 返回条数限制

        Returns:
            消息列表
        """
        try:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(SessionMessageModel)
                    .where(SessionMessageModel.session_id == session_id)
                    .order_by(SessionMessageModel.created_at.asc())
                    .limit(limit)
                )
                messages = result.scalars().all()
                return [
                    {
                        "id": msg.id,
                        "session_id": msg.session_id,
                        "role": msg.role,
                        "content": msg.content,
                        "tool_call_id": msg.tool_call_id,
                        "created_at": msg.created_at,
                        "updated_at": msg.updated_at,
                        "first_token_duration_ms": msg.first_token_duration_ms,
                        "total_duration_ms": msg.total_duration_ms,
                    }
                    for msg in messages
                ]
        except Exception as e:
            logger.error(f"[SessionService] Error getting session history: {e}")
            return []

    async def get_session_events(
        self,
        session_id: str,
        session_message_id: Optional[str] = None,
    ) -> list[dict]:
        """获取会话事件.

        Args:
            session_id: 会话ID
            session_message_id: 消息ID（可选）

        Returns:
            事件列表
        """
        try:
            async with async_session_factory() as session:
                query = select(SessionEventModel).where(
                    SessionEventModel.session_id == session_id
                )
                if session_message_id:
                    query = query.where(
                        SessionEventModel.session_message_id == session_message_id
                    )
                query = query.order_by(SessionEventModel.created_at.asc())

                result = await session.execute(query)
                events = result.scalars().all()
                return [
                    {
                        "id": event.id,
                        "session_id": event.session_id,
                        "session_message_id": event.session_message_id,
                        "event_body": event.event_body,
                        "created_at": event.created_at,
                        "has_error": event.has_error,
                        "user_query": event.user_query,
                        "duration_ms": event.duration_ms,
                    }
                    for event in events
                ]
        except Exception as e:
            logger.error(f"[SessionService] Error getting session events: {e}")
            return []


# 全局单例
session_service = SessionService()
