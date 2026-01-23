"""Session 相关的 SQLAlchemy Models."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Text, Boolean, Integer, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class SessionModel(Base):
    """会话表 Model."""

    __tablename__ = "session"
    __table_args__ = {"schema": "ttd"}

    id: Mapped[str] = mapped_column(String(30), primary_key=True, default=lambda: uuid.uuid4().hex[:30])
    user_sid: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class SessionMessageModel(Base):
    """会话消息表 Model."""

    __tablename__ = "session_message"
    __table_args__ = {"schema": "ttd"}

    id: Mapped[str] = mapped_column(String(30), primary_key=True, default=lambda: uuid.uuid4().hex[:30])
    session_id: Mapped[str] = mapped_column(
        String(30),
        ForeignKey("ttd.session.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user' | 'assistant' | 'system'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_call_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    first_token_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    referrer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    user_message_id: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)


class SessionEventModel(Base):
    """会话事件表 Model."""

    __tablename__ = "session_event"
    __table_args__ = {"schema": "ttd"}

    id: Mapped[str] = mapped_column(String(30), primary_key=True, default=lambda: uuid.uuid4().hex[:30])
    session_id: Mapped[str] = mapped_column(
        String(30),
        ForeignKey("ttd.session.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_message_id: Mapped[str] = mapped_column(
        String(30),
        ForeignKey("ttd.session_message.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_body: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    has_error: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    one_ci_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
