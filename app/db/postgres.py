import psycopg2
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from loguru import logger
from config import get_settings

settings = get_settings()


class PostgreSQLClient:
    """PostgreSQL 客户端 - 用于元数据存储."""

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
                    columns = [desc[0] for desc in cursor.description]
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

    def save_query_history(
        self,
        session_id: str,
        user_query: str,
        generated_sql: str,
        execution_result: Optional[str] = None,
        error: Optional[str] = None,
    ) -> int:
        """保存查询历史."""
        sql = """
            INSERT INTO query_history
            (session_id, user_query, generated_sql, execution_result, error)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """
        result = self.execute_query(sql, (session_id, user_query, generated_sql, execution_result, error))
        return result[0]["id"]

    def get_query_history(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取查询历史."""
        sql = """
            SELECT id, session_id, user_query, generated_sql, execution_result, error, created_at
            FROM query_history
            WHERE session_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        return self.execute_query(sql, (session_id, limit))

    def get_session_context(self, session_id: str) -> List[Dict[str, Any]]:
        """获取会话上下文."""
        return self.get_query_history(session_id, limit=20)


# 全局实例
pg_client = PostgreSQLClient()
