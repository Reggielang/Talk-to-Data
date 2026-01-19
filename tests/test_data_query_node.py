"""DataQuery 节点测试."""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import datetime
from app.graph.node.data_query import data_query_node, data_query_node_simple
from app.conf.prompt_init import PromptConfig
from app.conf.utils.prompt_parms import create_date_function


def test_prompt_rendering():
    """测试模板渲染."""
    print("=" * 60)
    print("测试 data_query_system.j2 模板渲染")
    print("=" * 60)

    prompt_config = PromptConfig()
    date_func = create_date_function()

    result = prompt_config.render(
        "data_query_system.j2",
        date=date_func,
        task="请查询近30天幽灵党影片的点击次数是多少？"
    )

    print(result)
    print("\n" + "=" * 60)


def test_date_function():
    """测试日期函数."""
    print("=" * 60)
    print("测试日期函数")
    print("=" * 60)

    date_func = create_date_function()

    print(f"当前年月: {date_func('Y-m')}")
    print(f"本年: {date_func('Y')}")
    print(f"本月: {date_func('Y')}-{date_func('m')}")
    print(f"上个月: {date_func('Y-m', 'Month-1')}")
    print(f"今天: {date_func('Y-m-d')}")
    print(f"近30天开始: {date_func('Y-m-d', 'Day-29')}")
    print(f"本周开始: {date_func('Y-m-d', 'WeekBegin')}")
    print(f"本周结束: {date_func('Y-m-d', 'WeekEnd')}")

    print("\n" + "=" * 60)


def test_sql_extraction():
    """测试 SQL 提取."""
    print("=" * 60)
    print("测试 SQL 提取")
    print("=" * 60)

    from app.graph.node.data_query import capture_sql_blocks

    test_cases = [
        # 标准 SQL 代码块
        '这是一些文本\n```sql\nSELECT * FROM users\n```',
        # 多个 SQL 代码块
        '```sql\nSELECT 1\n```\n```sql\nSELECT 2\n```',
        # 没有语言标识的代码块
        '```\nSELECT * FROM table\n```',
    ]

    for i, test in enumerate(test_cases, 1):
        sqls = capture_sql_blocks(test)
        print(f"测试 {i}: 找到 {len(sqls)} 个 SQL 代码块")
        for sql in sqls:
            print(f"  SQL: {sql.strip()}")

    print("\n" + "=" * 60)


def test_data_query_node():
    """测试 DataQuery 节点."""
    print("=" * 60)
    print("测试 DataQuery 节点")
    print("=" * 60)

    # 创建模拟的 State
    state = {
        "SessionId": "test_session",
        "SessionMessgeId": "test_msg_id",
        "UserQuery": "请查询近30天幽灵党影片的点击次数是多少？",
        "LlmModelName": "qwen-max",
        "LlmTemperature": 0.1,
        "Messages": [],
        "SupervisorMessages": [],
        "CurrentDatetime": datetime.datetime.now(),
        "LlmCalls": [],
        "ForceEnd": False,
        "IsBlocked": False,
        "BlockReason": "",
        "UnderstandResult": {},
        "Response": "",
        "UserRole": "MR",
        "DataQueryTask": "请查询近30天幽灵党影片的点击次数是多少？",
        "DataQueryTable": "app.content_analysis",
        "DataQueryModule": "default",
        "SqlGenResult": {},
        "DataQueryResult": {},
    }

    # 调用节点
    result = data_query_node_simple(state)

    print(f"生成的 SQL: {result.get('SqlGenResult', {}).get('Sql', 'N/A')}")
    print(f"查询结果行数: {result.get('DataQueryResult', {}).get('DataRowLength', 0)}")
    print(f"响应: {result.get('Response', 'N/A')[:200]}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    import io
    # 设置 UTF-8 输出
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    # 运行测试
    test_date_function()
    test_prompt_rendering()
    test_sql_extraction()
    # test_data_query_node()  # 需要 LLM 服务才能运行
