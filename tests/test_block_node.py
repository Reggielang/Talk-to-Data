"""测试 BLOCK 节点."""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.graph.node.block import block_node
from app.graph.core.state import State
from app.graph.core.model import MessageItem, LlmCallItem
from loguru import logger
import datetime


def create_test_state(user_query: str, messages: list = None) -> State:
    """创建测试用的 State."""
    return State(
        SessionId="test-session-001",
        SessionMessgeId="test-msg-001",
        UserQuery=user_query,
        LlmModelName="glm-4.7",
        LlmTemperature=0.0,
        Messages=messages or [],
        SupervisorMessages=[],
        CurrentDatetime=datetime.datetime.now(),
        LlmCalls=[],
        ForceEnd=False,
        IsBlocked=False,
        BlockReason="",
        Response="",
    )


def run_test(user_query: str, description: str):
    """运行单个测试."""
    print("=" * 80)
    print(f"测试: {description}")
    print(f"用户问题: {user_query}")
    print("=" * 80)

    state = create_test_state(user_query)

    try:
        result_state = block_node(state)

        print(f"\n结果:")
        print(f"  是否被拦截: {result_state['IsBlocked']}")
        print(f"  拦截原因: {result_state['BlockReason']}")
        if result_state['Response']:
            print(f"  响应: {result_state['Response'][:100]}...")

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()

    print()


if __name__ == "__main__":
    # 设置 UTF-8 输出
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    # 测试用例
    test_cases = [
        # 1. 正常的数据查询
        ("查询所有用户", "正常数据查询"),

        # 2. 问候
        ("你好", "问候语"),

        # 3. 天气查询 (应该被拦截 - irrelevant)
        ("今天天气怎么样", "闲聊 - 天气"),

        # 4. 工资相关 (应该被拦截 - salary)
        ("员工工资是多少", "工资问题"),

        # 5. 不清楚的问题
        ("查询dupi", "不清楚的问题"),

        # 6. 带历史消息的查询
        ("统计用户总数", "带历史消息的查询"),
    ]

    # 创建带历史消息的状态
    history_state = State(
        SessionId="test-session-002",
        SessionMessgeId="test-msg-002",
        UserQuery="统计用户总数",
        LlmModelName="glm-4.7",
        LlmTemperature=0.0,
        Messages=[
            MessageItem(Role="user", Content="你好"),
            MessageItem(Role="assistant", Content="你好！我是数据查询助手"),
        ],
        SupervisorMessages=[],
        CurrentDatetime=datetime.datetime.now(),
        LlmCalls=[],
        ForceEnd=False,
        IsBlocked=False,
        BlockReason="",
        Response="",
    )

    # 运行测试
    for query, desc in test_cases[:5]:  # 跳过带历史消息的测试
        run_test(query, desc)

    # 测试带历史消息的情况
    print("=" * 80)
    print(f"测试: 带历史消息的查询")
    print(f"用户问题: {history_state['UserQuery']}")
    print(f"历史消息: {len(history_state['Messages'])} 条")
    print("=" * 80)

    try:
        result_state = block_node(history_state)
        print(f"\n结果:")
        print(f"  是否被拦截: {result_state['IsBlocked']}")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
