import psycopg2
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from datetime import datetime, timezone
from loguru import logger
from app.conf.config import settings
import uuid
import json


class PostgreSQLClient:
    """PostgreSQL 客户端 - 用于存储会话事件和消息.

    Session 的创建和管理由 FastAPI 层负责，这里只负责存储执行过程中的事件和消息。
    """

    def __init__(self):
        self.config = {
            "host": settings.pg_host,
            "port": settings.pg_port,
            "user": settings.pg_user,
            "password": settings.pg_password,
            "database": settings.pg_database,
        }

    @contextmanager
    def get_connection(self):
        """获取数据库连接上下文."""
        conn = psycopg2.connect(**self.config)
        try:
            yield conn
        finally:
            conn.close()

    def execute_query(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """执行查询."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, params or ())
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    result = [dict(zip(columns, row)) for row in cursor.fetchall()]
                conn.commit()
                return result
        except Exception as e:
            logger.error(f"PostgreSQL query error: {e}")
            raise

    def execute_sql(self, sql: str, params: Optional[tuple] = None) -> bool:
        """执行非查询 SQL."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, params or ())
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"PostgreSQL execute error: {e}")
            raise

    # ==================== Session 相关 ====================

    def create_session(
        self,
        namespace_id: str,
        user_sid: str,
        user_email: str,
        note: Optional[str] = None,
        expired_days: int = 7,
    ) -> str:
        """创建新会话（用于测试）."""
        session_id = uuid.uuid4().hex[:30]
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        expired_at = now + timedelta(days=expired_days)

        sql = """
            INSERT INTO ttd.session
            (id, namespace_id, user_sid, user_email, note, created_at, updated_at, expired_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        result = self.execute_query(
            sql,
            (
                session_id,
                namespace_id,
                user_sid,
                user_email,
                note,
                now,
                now,
                expired_at,
            ),
        )
        return result[0]["id"]

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息."""
        sql = """
            SELECT id, namespace_id, user_sid, user_email, note, created_at, updated_at, expired_at
            FROM ttd.session
            WHERE id = %s
        """
        result = self.execute_query(sql, (session_id,))
        return result[0] if result else None

    # ==================== Session Message 相关 ====================

    def create_session_message(
        self,
        session_id: str,
        namespace_id: str,
        role: str,
        content: str,
        tool_call_id: Optional[str] = None,
        user_email: Optional[str] = None,
        user_message_id: Optional[str] = None,
        first_token_duration_ms: Optional[int] = None,
        total_duration_ms: Optional[int] = None,
        referrer: Optional[str] = None,
    ) -> str:
        """创建会话消息."""
        message_id = uuid.uuid4().hex[:30]
        now = datetime.now(timezone.utc)

        sql = """
            INSERT INTO ttd.session_message
            (id, session_id, role, content, tool_call_id, created_at, updated_at,
             namespace_id, first_token_duration_ms, total_duration_ms, referrer,
             user_email, user_message_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        result = self.execute_query(
            sql,
            (
                message_id,
                session_id,
                role,
                content,
                tool_call_id,
                now,
                now,
                namespace_id,
                first_token_duration_ms,
                total_duration_ms,
                referrer,
                user_email,
                user_message_id,
            ),
        )
        return result[0]["id"]

    def get_session_messages(
        self, session_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取会话消息列表."""
        sql = """
            SELECT id, session_id, role, content, tool_call_id, created_at, updated_at,
                   first_token_duration_ms, total_duration_ms
            FROM ttd.session_message
            WHERE session_id = %s
            ORDER BY created_at ASC
            LIMIT %s
        """
        return self.execute_query(sql, (session_id, limit))

    # ==================== Session Event 相关 ====================

    def create_session_event(
        self,
        namespace_id: str,
        session_id: str,
        session_message_id: str,
        user_email: str,
        event_body: Dict[str, Any],
        user_query: str = "",
        one_ci_params: Optional[Dict[str, Any]] = None,
        duration_ms: int = 0,
        has_error: bool = False,
    ) -> str:
        """创建单个会话事件."""
        event_id = uuid.uuid4().hex[:30]
        now = datetime.now(timezone.utc)

        sql = """
            INSERT INTO ttd.session_event
            (id, namespace_id, session_id, session_message_id, user_email,
             event_body, created_at, has_error, user_query, one_ci_params, duration_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        result = self.execute_query(
            sql,
            (
                event_id,
                namespace_id,
                session_id,
                session_message_id,
                user_email,
                json.dumps(event_body, ensure_ascii=False, default=str),
                now,
                has_error,
                user_query,
                json.dumps(one_ci_params, ensure_ascii=False) if one_ci_params else None,
                duration_ms,
            ),
        )
        return result[0]["id"]

    def create_session_event_batch(
        self,
        namespace_id: str,
        session_id: str,
        session_message_id: str,
        user_email: str,
        events: List[Dict[str, Any]],
        user_query: str = "",
        one_ci_params: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """批量创建会话事件.

        Args:
            namespace_id: 命名空间ID
            session_id: 会话ID
            session_message_id: 会话消息ID
            user_email: 用户邮箱
            events: 事件列表，每个事件包含 NodeName, Type, CurrentState, LlmCalls, Timestamp 等
            user_query: 用户查询
            one_ci_params: 其他参数

        Returns:
            事件ID列表
        """
        event_ids = []

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                for event in events:
                    event_id = uuid.uuid4().hex[:30]
                    event_ids.append(event_id)

                    # 计算 duration_ms（从事件开始到当前时间）
                    start_time = event.get("Timestamp")
                    if start_time and isinstance(start_time, datetime):
                        duration_ms = int(
                            (datetime.now(timezone.utc) - start_time.replace(tzinfo=timezone.utc)).total_seconds() * 1000
                        )
                    else:
                        duration_ms = 0

                    # 判断是否有错误
                    has_error = event.get("Type") == "ERROR" or event.get("Error") is not None

                    sql = """
                        INSERT INTO ttd.session_event
                        (id, namespace_id, session_id, session_message_id, user_email,
                         event_body, created_at, has_error, user_query, one_ci_params, duration_ms)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(
                        sql,
                        (
                            event_id,
                            namespace_id,
                            session_id,
                            session_message_id,
                            user_email,
                            json.dumps(event, ensure_ascii=False, default=str),
                            datetime.now(timezone.utc),
                            has_error,
                            user_query,
                            json.dumps(one_ci_params, ensure_ascii=False) if one_ci_params else None,
                            duration_ms,
                        ),
                    )

                conn.commit()

        return event_ids

    def get_session_events(
        self, session_id: str, session_message_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取会话事件列表."""
        if session_message_id:
            sql = """
                SELECT id, session_id, session_message_id, event_body, created_at,
                       has_error, user_query, duration_ms
                FROM ttd.session_event
                WHERE session_id = %s AND session_message_id = %s
                ORDER BY created_at ASC
            """
            return self.execute_query(sql, (session_id, session_message_id))
        else:
            sql = """
                SELECT id, session_id, session_message_id, event_body, created_at,
                       has_error, user_query, duration_ms
                FROM ttd.session_event
                WHERE session_id = %s
                ORDER BY created_at ASC
            """
            return self.execute_query(sql, (session_id,))


# 全局实例
pg_client = PostgreSQLClient()
