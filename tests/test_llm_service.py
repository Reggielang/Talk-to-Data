"""测试 LLM 服务."""
import sys
from pathlib import Path
from app.conf.utils.prompt_parms import create_date_function

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.graph.core.state import State
from app.services.llm_service import llm_service, LlmRequest
from langchain_core.messages import HumanMessage, SystemMessage,AIMessage
from loguru import logger
from app.conf.prompt_init import prompt_template_service

def test_simple_chat():
    """测试简单聊天."""
    print("=" * 80)

    request = LlmRequest(
        messages=[
            HumanMessage(content="你好，请用一句话介绍你自己。")
        ]
    )

    try:
        content, usage = llm_service.simple_chat(request)
        print(f"\n回复: {content}")
        if usage:
            print(f"Token 使用: {usage}")
        print("✓ 简单聊天测试通过\n")
        return True
    except Exception as e:
        print(f"✗ 简单聊天测试失败: {e}\n")
        return False


def test_simple_json_output(user_query="请查询近30天幽灵党影片的点击次数是多少？"):
    """测试 JSON 输出."""
    print("=" * 80)
    print("测试 2: JSON 输出")

    # 1. 渲染提示词模板
    date_func = create_date_function()
    block_user_prompt = prompt_template_service.render(
        "data_query_system.j2",
        # messages=state.get("Messages", []),
        date=date_func,
        task=user_query,
    )

    # 2. 构建消息
    messages = [
        SystemMessage(content=block_user_prompt),
        HumanMessage(content=user_query),
    ]
    try:
        result, usage = llm_service.simple_chat(request=LlmRequest(messages=messages))
        print(f"\nJSON 结果:")
        print(result)
        print("✓ JSON 输出测试通过\n")
        return True
    except Exception as e:
        print(f"✗ JSON 输出测试失败: {e}\n")
        import traceback
        traceback.print_exc()
        return False





if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("LLM 服务测试")
    print("=" * 80 + "\n")

    results = []

    # 运行所有测试
    # results.append(("简单聊天", test_simple_chat()))

    results.append(("JSON 输出", test_simple_json_output()))