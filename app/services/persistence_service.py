"""异步持久化服务 - 负责将会话数据异步存储到数据库."""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from loguru import logger
from typing import Optional

from app.db.models import SessionMessageModel, SessionEventModel
from app.db.base import async_session_factory
from app.services.session_service import session_service


def _truncate_id(id_value: Optional[str], max_length: int = 30) -> Optional[str]:
    """截断 ID 到指定长度，防止数据库字段超长."""
    if id_value is None:
        return None
    return id_value[:max_length] if len(id_value) > max_length else id_value


class PersistenceService:
    """异步持久化服务 - 使用后台任务保存会话数据."""

    def __init__(self):
        """初始化持久化服务."""
        self._background_tasks = set()

    def save_session_data_async(
        self,
        session_id: str,
        session_message_id: str,
        user_email: str,
        user_query: str,
        final_state: dict,
        event_collector,
    ) -> None:
        """异步保存会话数据（消息 + 事件）.

        Args:
            session_id: 会话ID
            session_message_id: 会话消息ID
            user_email: 用户邮箱
            user_query: 用户查询
            final_state: 最终状态
            event_collector: 事件收集器
        """
        # 创建后台任务
        task = asyncio.create_task(
            self._save_session_data(
                session_id=session_id,
                session_message_id=session_message_id,
                user_email=user_email,
                user_query=user_query,
                final_state=final_state,
                event_collector=event_collector,
            )
        )
        # 添加到任务集合，防止被垃圾回收
        self._background_tasks.add(task)
        # 任务完成后自动从集合中移除
        task.add_done_callback(self._background_tasks.discard)

    async def _save_session_data(
        self,
        session_id: str,
        session_message_id: str,
        user_email: str,
        user_query: str,
        final_state: dict,
        event_collector,
    ) -> None:
        """实际保存会话数据的后台任务."""
        try:
            # 截断 ID 防止数据库字段超长
            session_id = _truncate_id(session_id, 30)
            session_message_id = _truncate_id(session_message_id, 30)

            logger.info(f"[PersistenceService] Saving session data for {session_id}/{session_message_id}")

            # 1. 确保会话存在（使用异步 session_service）
            await session_service.ensure_session_exists(
                session_id=session_id,
                user_email=user_email,
            )
            logger.info(f"[PersistenceService] Session ensured: {session_id}")

            # 2. 保存用户消息
            await self._create_message(
                session_id=session_id,
                role="user",
                content=user_query,
                user_email=user_email,
                user_message_id=session_message_id,
            )

            # 3. 保存助手回复消息（如果有）
            summarize_result = final_state.get("SummarizeResult", "")
            if summarize_result:
                llm_calls = final_state.get("LlmCalls", [])
                first_token_duration_ms = None
                total_duration_ms = None

                if llm_calls:
                    last_call = llm_calls[-1]
                    first_token_duration_ms = last_call.get("FirstTokenDurationMs")
                    total_duration_ms = last_call.get("TotalDurationMs")

                await self._create_message(
                    session_id=session_id,
                    role="assistant",
                    content=summarize_result,
                    user_email=user_email,
                    first_token_duration_ms=first_token_duration_ms,
                    total_duration_ms=total_duration_ms,
                )

            # 4. 批量保存事件
            events = event_collector.get_events()
            if events:
                await self._create_events_batch(
                    session_id=session_id,
                    session_message_id=session_message_id,
                    user_email=user_email,
                    events=events,
                    user_query=user_query,
                )

            logger.info(f"[PersistenceService] Successfully saved session data for {session_id}/{session_message_id}")

        except Exception as e:
            logger.error(f"[PersistenceService] Error saving session data: {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def _create_message(
        self,
        session_id: str,
        role: str,
        content: str,
        user_email: str,
        user_message_id: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        first_token_duration_ms: Optional[int] = None,
        total_duration_ms: Optional[int] = None,
    ) -> str:
        """创建会话消息."""
        # 截断所有 ID 防止数据库字段超长
        session_id = _truncate_id(session_id, 30)
        user_message_id = _truncate_id(user_message_id, 30)
        message_id = user_message_id if user_message_id else _truncate_id(uuid.uuid4().hex, 30)
        now = datetime.now(timezone.utc)

        try:
            async with async_session_factory() as session:
                message = SessionMessageModel(
                    id=message_id,
                    session_id=session_id,
                    role=role,
                    content=content,
                    tool_call_id=tool_call_id,
                    created_at=now,
                    updated_at=now,
                    first_token_duration_ms=first_token_duration_ms,
                    total_duration_ms=total_duration_ms,
                    user_email=user_email,
                    user_message_id=user_message_id,
                )
                session.add(message)
                await session.commit()
                await session.refresh(message)
                return message.id
        except Exception as e:
            logger.error(f"[PersistenceService] Error creating message: {e}")
            raise

    def _clean_event_for_json(self, event: dict) -> dict:
        """清理 event 中的不可 JSON 序列化的对象（如 datetime）.

        使用 json.dumps + json.loads 方式，比递归深拷贝更高效.

        Args:
            event: 原始事件字典

        Returns:
            可 JSON 序列化的事件字典
        """
        return json.loads(json.dumps(event, default=str))

    async def _create_events_batch(
        self,
        session_id: str,
        session_message_id: str,
        user_email: str,
        events: list[dict],
        user_query: str = "",
    ) -> list[str]:
        """批量创建会话事件."""
        event_ids = []

        # 截断所有 ID 防止数据库字段超长
        session_id = _truncate_id(session_id, 30)
        session_message_id = _truncate_id(session_message_id, 30)

        try:
            async with async_session_factory() as session:
                for event in events:
                    event_id = _truncate_id(uuid.uuid4().hex, 30)
                    event_ids.append(event_id)

                    # 计算 duration_ms
                    start_time = event.get("Timestamp")
                    if start_time and isinstance(start_time, datetime):
                        duration_ms = int(
                            (datetime.now(timezone.utc) - start_time.replace(tzinfo=timezone.utc)).total_seconds() * 1000
                        )
                    else:
                        duration_ms = 0

                    # 判断是否有错误
                    has_error = event.get("Type") == "ERROR" or event.get("Error") is not None

                    # 清理 event 中的 datetime 对象，转换为可 JSON 序列化的格式
                    cleaned_event = self._clean_event_for_json(event)

                    event_model = SessionEventModel(
                        id=event_id,
                        session_id=session_id,
                        session_message_id=session_message_id,
                        user_email=user_email,
                        event_body=cleaned_event,  # 使用清理后的字典
                        created_at=datetime.now(timezone.utc),
                        has_error=has_error,
                        user_query=user_query,
                        one_ci_params=None,
                        duration_ms=duration_ms,
                    )
                    session.add(event_model)

                await session.commit()
                return event_ids

        except Exception as e:
            logger.error(f"[PersistenceService] Error creating events batch: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise


# 全局单例
persistence_service = PersistenceService()
