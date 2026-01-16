"""
初始化 PostgreSQL 元数据库脚本.
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.postgres import pg_client
from config import get_settings

settings = get_settings()


def init_database():
    """初始化数据库表."""
    sql_commands = [
        # 查询历史表
        """
        CREATE TABLE IF NOT EXISTS query_history (
            id SERIAL PRIMARY KEY,
            session_id VARCHAR(255) NOT NULL,
            user_query TEXT NOT NULL,
            generated_sql TEXT NOT NULL,
            execution_result TEXT,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_session_id (session_id),
            INDEX idx_created_at (created_at)
        );
        """,

        # Schema 缓存表
        """
        CREATE TABLE IF NOT EXISTS schema_cache (
            id SERIAL PRIMARY KEY,
            table_name VARCHAR(255) NOT NULL UNIQUE,
            column_info JSONB NOT NULL,
            description TEXT,
            embedding VECTOR(1536),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,

        # 用户反馈表
        """
        CREATE TABLE IF NOT EXISTS user_feedback (
            id SERIAL PRIMARY KEY,
            query_history_id INTEGER REFERENCES query_history(id),
            feedback INTEGER NOT NULL CHECK (feedback >= 1 AND feedback <= 5),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    ]

    for sql in sql_commands:
        try:
            pg_client.execute_sql(sql)
            print(f"✓ 表创建成功")
        except Exception as e:
            print(f"✗ 创建失败: {e}")

    print("\n初始化完成!")


if __name__ == "__main__":
    print(f"连接到 PostgreSQL: {settings.pg_host}:{settings.pg_port}/{settings.pg_database}")
    print("初始化元数据库...\n")
    init_database()
