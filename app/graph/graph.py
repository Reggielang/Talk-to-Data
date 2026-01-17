from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, START,END
from langchain_core.messages import HumanMessage, AIMessage
import operator
from loguru import logger
from app.graph.node import block, understand
from app.graph.core.state import State


def create_state_graph() -> StateGraph[State]:
    """创建对话状态图."""
    graph = StateGraph(State)

    # 添加 节点
    graph.add_node("BLOCK", block.block_node)
    graph.add_node("UNDERSTAND", understand.understand_node)

    # 定义节点之间的连接关系
    graph.add_edge(START, "BLOCK")
    graph.add_edge("BLOCK", "UNDERSTAND")
    graph.add_edge("UNDERSTAND", END)

    return graph

    # 生成PNG图片
    logger.info("\n=== 生成流程图PNG ===")
    try:
        app.get_graph().draw_mermaid_png(output_file_path="app_graph.png")
        print("流程图已保存为 app_graph.png")
        mermaid = app.get_graph().draw_mermaid()
        print("Mermaid代码：")
        print(mermaid)
    except Exception as e:
        print(f"生成PNG图片失败: {e}")
        try:
            mermaid = app.get_graph().draw_mermaid()
            print("Mermaid代码：")
            print(mermaid)
        except Exception as e2:
            logger.error(f"Failed to draw Mermaid: {e2}")

    return graph

# 编译图
workflow = create_state_graph()
app = workflow.compile()