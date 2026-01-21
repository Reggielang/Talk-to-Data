import json
from datetime import datetime
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from loguru import logger
from app.graph.core.state import State
from app.conf.prompt_init import PromptConfig
from app.conf.utils.prompt_parms import create_date_function
from app.services.llm_service import llm_service, LlmRequest
from app.db.mysql import mysql_client
from decimal import Decimal
def execute_sql_query(sql: str) -> tuple[str, str, int]:
    """执行 SQL 查询.

    Args:
        sql: SQL 查询语句

    Returns:
        (json_content, sample_json_content, data_length)
    """
    logger.info(f"Executing SQL: {sql}")

    try:
        # 使用 mysql_client 执行查询
        results = mysql_client.execute_query(sql)
        data_length = len(results)

        if data_length == 0:
            return "[]", "[]", 0
        
        def decimal_default(obj):
            if isinstance(obj, Decimal):
                return float(obj)  # 转换为浮点数
            raise TypeError(f"Type {type(obj)} not serializable")
        # 直接使用自定义 encoder 转换为 JSON 字符串
        json_content = json.dumps(results, default=decimal_default,ensure_ascii=False)

        # 生成样本数据（最多 5 条）
        sample_size = min(5, len(results))
        sample_data = results[:sample_size]
        sample_json_content = json.dumps(sample_data,default=decimal_default, indent=2,ensure_ascii=False)

        logger.info(f"Query executed successfully. Rows: {data_length}")

        return json_content, sample_json_content, data_length
    except Exception as e:
        logger.error(f"Error executing SQL: {e}")
        raise

if __name__ == "__main__":
    # 测试执行 SQL 查询
    test_sql = """
            #Description: 查询近30天幽灵党影片的点击次数。 --content_name: 内容名称 --total_clicks_last_30_days: 近30天累计点击次数       
            SELECT
                content_name,
                SUM(click_count) AS total_clicks_last_30_days
            FROM
                app.content_analysis
            WHERE
                content_name LIKE '%幽灵党%'
            AND stat_date >= '2025-12-22'
            AND stat_date <= '2026-01-20'
            GROUP BY content_name
            ORDER BY total_clicks_last_30_days DESC
            """
    json_content, sample_json_content, data_length = execute_sql_query(test_sql)
    print(f"Data Length: {data_length}")
    print(f"JSON Content: {json_content}")
    print(f"Sample JSON Content: {sample_json_content}")