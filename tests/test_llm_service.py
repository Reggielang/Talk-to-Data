"""测试 LLM 服务."""
import sys
from pathlib import Path

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
    print("测试 1: 简单聊天")
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


def test_simple_json_output(user_query="今天天气怎么样"):
    """测试 JSON 输出."""
    print("=" * 80)
    print("测试 2: JSON 输出")
    print("=" * 80)

    # 1. 渲染提示词模板
    block_system_prompt = prompt_template_service.render("block_system.j2")

    block_user_prompt = prompt_template_service.render(
        "block_user.j2",
        # messages=state.get("Messages", []),
        question=user_query,
    )

    # 2. 构建消息
    messages = [
        SystemMessage(content=block_system_prompt),
        HumanMessage(content=block_user_prompt),
    ]
    try:
        result, usage = llm_service.simple_json_output(request=LlmRequest(messages=messages))
        print(f"\nJSON 结果:")
        print(result)
        print("✓ JSON 输出测试通过\n")
        return True
    except Exception as e:
        print(f"✗ JSON 输出测试失败: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_block_classification():
    """测试 BLOCK 节点分类."""
    print("=" * 80)
    print("测试 3: BLOCK 节点分类")
    print("=" * 80)

    # 测试用例
    test_cases = [
        ("查询所有用户", "正常数据查询"),
        ("你好", "问候语"),
        ("今天天气怎么样", "闲聊 - 应该被拦截"),
        ("员工工资是多少", "工资问题 - 应该被拦截"),
    ]

    for query, desc in test_cases:
        print(f"\n[{desc}]")
        print(f"问题: {query}")

        request = LlmRequest(
            messages=[
                SystemMessage(content="你是一个问题分类助理，严格按照 JSON 格式返回分类结果。"),
                HumanMessage(content=f"用户问题: {query}\n你的回答:")
            ]
        )

        try:
            result, _ = llm_service.simple_json_output(request)
            category = result.get("category", "unknown")
            message = result.get("message", "")

            print(f"  分类: {category}")
            if message:
                print(f"  消息: {message[:50]}...")

        except Exception as e:
            print(f"  错误: {e}")


def test_multi_turn_conversation():
    """测试多轮对话."""
    print("\n" + "=" * 80)
    print("测试 4: 多轮对话")
    print("=" * 80)

    request = LlmRequest(
        messages=[
            SystemMessage(content="你是一个友好的助手。"),
            HumanMessage(content="我叫小明"),
            AIMessage(content="你好小明！很高兴认识你。"),
            HumanMessage(content="你还记得我的名字吗？"),
        ]
    )

    try:
        content, _ = llm_service.simple_chat(request)
        print(f"\n回复: {content}")
        print("✓ 多轮对话测试通过\n")
        return True
    except Exception as e:
        print(f"✗ 多轮对话测试失败: {e}\n")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("LLM 服务测试")
    print("=" * 80 + "\n")

    results = []

    # 运行所有测试
    # results.append(("简单聊天", test_simple_chat()))

    results.append(("JSON 输出", test_simple_json_output()))
    # results.append(("多轮对话", test_multi_turn_conversation()))

    # # BLOCK 分类测试
    # test_block_classification()

    # # 汇总结果
    # print("=" * 80)
    # print("测试结果汇总")
    # print("=" * 80)

    # passed = sum(1 for _, result in results if result)
    # total = len(results)

    # for name, result in results:
    #     status = "✓ 通过" if result else "✗ 失败"
    #     print(f"{name}: {status}")

    # print(f"\n总计: {passed}/{total} 通过")