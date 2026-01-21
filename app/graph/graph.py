from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
import operator
import datetime
from loguru import logger
from app.graph.node import block, understand, data_query, postprocess, summary, supervisor
from app.graph.node.supervisor import route_from_supervisor
from app.graph.core.state import State


def create_state_graph(checkpointer=None) -> StateGraph[State]:
    """创建对话状态图."""
    graph = StateGraph(State)

    # 添加节点
    graph.add_node("BLOCK", block.block_node)
    graph.add_node("UNDERSTAND", understand.understand_node)
    graph.add_node("SUPERVISOR", supervisor.supervisor_node)
    graph.add_node("DATA_QUERY", data_query.data_query_node)
    graph.add_node("POSTPROCESS", postprocess.postprocess_node)
    graph.add_node("SUMMARIZE", summary.summary_node)

    # 定义节点之间的连接关系
    graph.add_edge(START, "BLOCK")
    graph.add_edge("BLOCK", "UNDERSTAND")
    graph.add_edge("UNDERSTAND", "SUPERVISOR")

    # SUPERVISOR 根据工具调用路由到不同节点
    graph.add_conditional_edges(
        "SUPERVISOR",
        route_from_supervisor,
        {
            "query_data": "DATA_QUERY",
            "postprocess": "POSTPROCESS",
            "summarize": "SUMMARIZE",
            "end": END,
        }
    )

    # 执行完子任务后回到 SUPERVISOR
    graph.add_edge("DATA_QUERY", "SUPERVISOR")
    graph.add_edge("POSTPROCESS", "SUPERVISOR")

    # SUMMARIZE 是最终步骤
    graph.add_edge("SUMMARIZE", END)

    return graph


# 编译图（绑定 checkpointer）
checkpointer = MemorySaver()
app = create_state_graph().compile(checkpointer=checkpointer)


def create_initial_state(user_query: str, model_name: str = "glm-4.6") -> State:
    """创建初始状态."""
    return State(
        SessionId="test_session",
        SessionMessgeId="test_msg",
        UserQuery=user_query,
        LlmModelName=model_name,
        LlmTemperature=0.1,
        Messages=[],
        CurrentDatetime=datetime.datetime.now(),
        LlmCalls=[],
        ForceEnd=False,
        IsBlocked=False,
        BlockReason="",
        RephraseResult="",
        UnderstandResult={},
        DataQueryTask="",
        DataQueryTable="",
        SqlGenResult={},
        DataQueryResult={},
        PostProcessTask="",
        PostProcessDatasetId="",
        PostProcessResult={},
        SummarizeDatasetId="",
        SummarizeResult="",
        Datasets={},
        DataQueryRethinkTimes=0,
        PostprocessRethinkTimes=0,
    )


if __name__ == "__main__":
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

    # 测试 state graph
    test_question = "近30天幽灵党影片的点击次数是多少？"
    thread_id = f"test_thread_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

    logger.info(f"测试问题: {test_question}")

    initial_state = create_initial_state(test_question)
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    # 使用 stream 方式执行
    for event in app.stream(initial_state, config):
        for node_name, node_state in event.items():
            if node_name in ["__start__", "__end__"]:
                continue
            logger.info(f"[{node_name}] 完成")
