from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
import operator

from app.services.nl2sql import nl2sql_service
from app.db.mysql import mysql_client
from app.db.postgres import pg_client
from app.db.redis import redis_client
from loguru import logger


class ConversationState(TypedDict):
    """对话状态."""
    messages: Annotated[list, operator.add]
    session_id: str
    user_query: str
    generated_sql: str
    query_result: list
    error: str
    response: str


def parse_query_node(state: ConversationState) -> ConversationState:
    """解析用户查询."""
    logger.info(f"Parsing query: {state['user_query']}")
    state["messages"] = state.get("messages", [])
    state["messages"] += [HumanMessage(content=state["user_query"])]
    return state


def generate_sql_node(state: ConversationState) -> ConversationState:
    """生成 SQL."""
    logger.info("Generating SQL...")

    # 获取会话上下文
    context = pg_client.get_session_context(state["session_id"])

    try:
        sql = nl2sql_service.convert(state["user_query"], context)
        state["generated_sql"] = sql
        state["messages"] += [AIMessage(content=f"Generated SQL: {sql}")]
    except Exception as e:
        state["error"] = str(e)
        state["response"] = f"抱歉，生成 SQL 时出错: {e}"
        state["messages"] += [AIMessage(content=state["response"])]

    return state


def execute_sql_node(state: ConversationState) -> ConversationState:
    """执行 SQL."""
    logger.info(f"Executing SQL: {state['generated_sql']}")

    try:
        result = mysql_client.execute_query(state["generated_sql"])
        state["query_result"] = result
        state["messages"] += [AIMessage(content=f"Query returned {len(result)} rows")]

        # 保存查询历史
        pg_client.save_query_history(
            session_id=state["session_id"],
            user_query=state["user_query"],
            generated_sql=state["generated_sql"],
            execution_result=str(len(result)),
        )
    except Exception as e:
        state["error"] = str(e)
        state["query_result"] = []
        state["messages"] += [AIMessage(content=f"Query error: {e}")]

        # 保存错误历史
        pg_client.save_query_history(
            session_id=state["session_id"],
            user_query=state["user_query"],
            generated_sql=state["generated_sql"],
            error=str(e),
        )

    return state


def format_response_node(state: ConversationState) -> ConversationState:
    """格式化响应."""
    logger.info("Formatting response...")

    if state.get("error"):
        state["response"] = f"查询出错: {state['error']}\n\n生成的 SQL:\n```sql\n{state['generated_sql']}\n```"
    elif not state["query_result"]:
        state["response"] = f"查询成功，但没有返回数据。\n\n执行的 SQL:\n```sql\n{state['generated_sql']}\n```"
    else:
        # 限制显示的行数
        display_rows = state["query_result"][:10]
        result_summary = f"查询成功！共 {len(state['query_result'])} 行数据。\n\n"

        if display_rows:
            # 获取列名
            columns = list(display_rows[0].keys())
            result_summary += "| " + " | ".join(columns) + " |\n"
            result_summary += "| " + " | ".join(["---"] * len(columns)) + " |\n"

            for row in display_rows:
                result_summary += "| " + " | ".join(str(v) for v in row.values()) + " |\n"

            if len(state["query_result"]) > 10:
                result_summary += f"\n... 还有 {len(state['query_result']) - 10} 行数据"

        result_summary += f"\n\n执行的 SQL:\n```sql\n{state['generated_sql']}\n```"
        state["response"] = result_summary

    state["messages"] += [AIMessage(content=state["response"])]

    # 更新 Redis 会话状态
    redis_client.save_session_state(state["session_id"], {
        "last_query": state["user_query"],
        "last_sql": state["generated_sql"],
        "message_count": len(state["messages"]),
    })

    return state


def should_continue(state: ConversationState) -> Literal["continue", "end"]:
    """决定是否继续."""
    if state.get("error"):
        return "end"
    return "end"


def create_conversation_graph():
    """创建对话图."""
    workflow = StateGraph(ConversationState)

    # 添加节点
    workflow.add_node("parse_query", parse_query_node)
    workflow.add_node("generate_sql", generate_sql_node)
    workflow.add_node("execute_sql", execute_sql_node)
    workflow.add_node("format_response", format_response_node)

    # 设置入口
    workflow.set_entry_point("parse_query")

    # 添加边
    workflow.add_edge("parse_query", "generate_sql")
    workflow.add_edge("generate_sql", "execute_sql")
    workflow.add_edge("execute_sql", "format_response")
    workflow.add_conditional_edges(
        "format_response",
        should_continue,
        {
            "continue": "parse_query",
            "end": END,
        }
    )

    return workflow.compile()


# 全局实例
conversation_graph = create_conversation_graph()
