"""
同步 MySQL Schema 到 PostgreSQL.
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.mysql import mysql_client
from app.db.postgres import pg_client
from config import get_settings

settings = get_settings()


def sync_schema():
    """同步 schema."""
    print(f"从 MySQL 获取 schema: {settings.mysql_database}")

    schema = mysql_client.get_schema()

    print(f"\n找到 {len(schema)} 个表:\n")

    for table_name, columns in schema.items():
        print(f"  - {table_name} ({len(columns)} columns)")

        # 插入或更新 schema 缓存
        sql = """
            INSERT INTO schema_cache (table_name, column_info, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (table_name)
            DO UPDATE SET
                column_info = EXCLUDED.column_info,
                updated_at = CURRENT_TIMESTAMP
        """

        try:
            import json
            pg_client.execute_sql(sql, (table_name, json.dumps(columns)))
            print(f"    ✓ 已同步")
        except Exception as e:
            print(f"    ✗ 同步失败: {e}")

    print("\n同步完成!")


if __name__ == "__main__":
    sync_schema()
