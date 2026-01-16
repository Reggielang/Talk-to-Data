import pymysql
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from loguru import logger
from conf.config import settings


class MySQLClient:
    """MySQL 客户端."""

    def __init__(self):
        self.config = {
            "host": settings.mysql_host,
            "port": settings.mysql_port,
            "user": settings.mysql_user,
            "password": settings.mysql_password,
            "database": settings.mysql_database,
            "charset": "utf8mb4",
            "cursorclass": pymysql.cursors.DictCursor,
        }

    @contextmanager
    def get_connection(self):
        """获取数据库连接上下文."""
        conn = pymysql.connect(**self.config)
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
                    result = cursor.fetchmany(settings.max_query_results)
                conn.commit()
                return result
        except Exception as e:
            logger.error(f"MySQL query error: {e}")
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
            logger.error(f"MySQL execute error: {e}")
            raise

    def get_schema(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取数据库 schema."""
        sql = """
            SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, COLUMN_COMMENT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME, ORDINAL_POSITION
        """
        results = self.execute_query(sql, (settings.mysql_database,))

        schema = {}
        for row in results:
            table = row["TABLE_NAME"]
            if table not in schema:
                schema[table] = []
            schema[table].append({
                "column": row["COLUMN_NAME"],
                "type": row["DATA_TYPE"],
                "comment": row["COLUMN_COMMENT"],
            })
        return schema

    def get_tables(self) -> List[str]:
        """获取所有表名."""
        sql = """
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s
            AND TABLE_TYPE = 'BASE TABLE'
        """
        results = self.execute_query(sql, (settings.mysql_database,))
        return [r["TABLE_NAME"] for r in results]


# 全局实例
mysql_client = MySQLClient()
