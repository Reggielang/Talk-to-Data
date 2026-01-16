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
    # 新增字段
    is_blocked: bool
    user_intent: str
    block_reason: str
    summary: str


def block_node(state: ConversationState) -> ConversationState:
    """BLOCK 节点 - 拦截不合规的问题."""
    logger.info(f"BLOCK node: Checking query: {state['user_query']}")

    # 初始化拦截状态
    state["is_blocked"] = False
    state["block_reason"] = ""

    query = state["user_query"].lower().strip()

    # 定义拦截规则
    block_rules = {
        "sensitive_topics": ["政治", "暴力", "色情", "赌博"],
        "invalid_queries": ["", " ", "\t", "\n"],
        "unsupported_commands": ["delete from", "drop table", "truncate table"],
    }

    # 检查敏感话题
    for topic in block_rules["sensitive_topics"]:
        if topic in query:
            state["is_blocked"] = True
            state["block_reason"] = f"抱歉，您的问题涉及敏感话题（{topic}），无法回答。"
            state["response"] = state["block_reason"]
            state["messages"] = state.get("messages", [])
            state["messages"] += [HumanMessage(content=state["user_query"])]
            state["messages"] += [AIMessage(content=state["response"])]
            logger.warning(f"Query blocked due to sensitive topic: {topic}")
            return state

    # 检查无效查询
    if query in block_rules["invalid_queries"]:
        state["is_blocked"] = True
        state["block_reason"] = "请输入有效的问题。"
        state["response"] = state["block_reason"]
        state["messages"] = state.get("messages", [])
        state["messages"] += [HumanMessage(content=state["user_query"])]
        state["messages"] += [AIMessage(content=state["response"])]
        logger.warning("Query blocked due to empty/invalid input")
        return state

    # 检查危险命令
    for cmd in block_rules["unsupported_commands"]:
        if cmd in query:
            state["is_blocked"] = True
            state["block_reason"] = f"抱歉，不支持执行 {cmd} 命令。"
            state["response"] = state["block_reason"]
            state["messages"] = state.get("messages", [])
            state["messages"] += [HumanMessage(content=state["user_query"])]
            state["messages"] += [AIMessage(content=state["response"])]
            logger.warning(f"Query blocked due to dangerous command: {cmd}")
            return state

    # 未被拦截
    state["messages"] = state.get("messages", [])
    state["messages"] += [HumanMessage(content=state["user_query"])]
    logger.info("Query passed BLOCK check")
    return state


def understand_node(state: ConversationState) -> ConversationState:
    """Understand 节点 - 理解用户意图."""
    logger.info("UNDERSTAND node: Analyzing user intent")

    query = state["user_query"].lower()

    # 简单的意图分类逻辑
    intent_patterns = {
        "data_query": ["查询", "显示", "多少", "统计", "列出", "show", "get", "find", "count", "list"],
        "data_aggregation": ["总计", "平均", "最大", "最小", "总和", "sum", "avg", "max", "min", "total"],
        "data_filter": ["筛选", "条件", "大于", "小于", "等于", "where", "filter", "greater", "less"],
        "greeting": ["你好", "hello", "hi", "您好"],
        "help": ["帮助", "help", "怎么用", "如何"],
    }

    detected_intent = "unknown"

    for intent, patterns in intent_patterns.items():
        if any(pattern in query for pattern in patterns):
            detected_intent = intent
            break

    state["user_intent"] = detected_intent
    state["messages"] += [AIMessage(content=f"Detected intent: {detected_intent}")]
    logger.info(f"User intent detected: {detected_intent}")

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


def supervisor_node(state: ConversationState) -> ConversationState:
    """Supervisor 节点 - 基于意图进行路由决策."""
    logger.info(f"SUPERVISOR node: Routing based on intent: {state['user_intent']}")

    # Supervisor 只做路由决策，不修改状态
    # 实际路由逻辑在 supervisor_route 函数中处理
    state["messages"] += [AIMessage(content=f"Supervisor routing for intent: {state['user_intent']}")]

    return state


def supervisor_route(state: ConversationState) -> Literal["generate_sql", "greeting_response", "help_response", "end"]:
    """Supervisor 路由函数 - 基于意图决定下一步."""
    intent = state.get("user_intent", "unknown")

    # 如果被拦截，直接结束
    if state.get("is_blocked", False):
        return "end"

    # 根据意图路由
    if intent == "greeting":
        return "greeting_response"
    elif intent == "help":
        return "help_response"
    elif intent in ["data_query", "data_aggregation", "data_filter"]:
        return "generate_sql"
    else:
        # 未知意图，尝试生成 SQL
        return "generate_sql"


def greeting_response_node(state: ConversationState) -> ConversationState:
    """处理问候."""
    logger.info("GREETING_RESPONSE node: Responding to greeting")

    greetings = [
        "您好！我是您的数据查询助手，请问有什么可以帮您的？",
        "你好！我可以帮您查询和分析数据，请告诉我您想了解什么。",
        "Hi！请问您想查询什么数据？",
    ]

    import random
    state["response"] = random.choice(greetings)
    state["messages"] += [AIMessage(content=state["response"])]

    return state


def help_response_node(state: ConversationState) -> ConversationState:
    """处理帮助请求."""
    logger.info("HELP_RESPONSE node: Providing help")

    help_text = """## 使用帮助

我可以帮您进行以下操作：

### 数据查询
- 示例："查询所有用户"
- 示例："显示最近的订单"

### 数据统计
- 示例："统计用户总数"
- 示例："计算平均销售额"

### 数据筛选
- 示例："查询年龄大于18的用户"
- 示例："找出状态为活跃的订单"

### 注意事项
- 不支持删除数据、删除表等危险操作
- 请用自然语言描述您的查询需求
"""

    state["response"] = help_text
    state["messages"] += [AIMessage(content=state["response"])]

    return state


def postprocess_node(state: ConversationState) -> ConversationState:
    """Postprocess 节点 - 后处理和格式化响应."""
    logger.info("POSTPROCESS node: Post-processing results")

    if state.get("error"):
        state["response"] = f"查询出错: {state['error']}\n\n生成的 SQL:\n```sql\n{state['generated_sql']}\n```"
    elif not state.get("query_result"):
        state["response"] = f"查询成功，但没有返回数据。\n\n执行的 SQL:\n```sql\n{state['generated_sql']}\n```"
    elif state.get("query_result"):
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

        logger.info(f"Post-processed {len(state['query_result'])} rows")
    else:
        # 非查询类响应（如问候、帮助等）已经设置了 response
        pass

    state["messages"] += [AIMessage(content=state.get("response", ""))]

    # 更新 Redis 会话状态
    redis_client.save_session_state(state["session_id"], {
        "last_query": state["user_query"],
        "last_sql": state.get("generated_sql", ""),
        "message_count": len(state["messages"]),
    })

    return state


def summary_node(state: ConversationState) -> ConversationState:
    """Summary 节点 - 生成总结."""
    logger.info("SUMMARY node: Generating summary")

    # 生成会话总结
    if state.get("is_blocked"):
        summary = f"查询被拦截: {state.get('block_reason', 'Unknown reason')}"
    elif state.get("error"):
        summary = f"查询执行出错: {state['error']}"
    elif state.get("query_result"):
        summary = f"成功执行查询，返回 {len(state['query_result'])} 行数据。"
    elif state.get("response"):
        summary = f"已生成响应: {state['response'][:50]}..."
    else:
        summary = "查询处理完成"

    state["summary"] = summary
    state["messages"] += [AIMessage(content=f"Summary: {summary}")]
    logger.info(f"Summary generated: {summary}")

    return state


def create_conversation_graph():
    """创建对话图."""
    workflow = StateGraph(ConversationState)

    # 添加节点
    workflow.add_node("block", block_node)
    workflow.add_node("understand", understand_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("generate_sql", generate_sql_node)
    workflow.add_node("execute_sql", execute_sql_node)
    workflow.add_node("postprocess", postprocess_node)
    workflow.add_node("summary", summary_node)
    workflow.add_node("greeting_response", greeting_response_node)
    workflow.add_node("help_response", help_response_node)

    # 设置入口
    workflow.set_entry_point("block")

    # 添加边
    workflow.add_edge("block", "understand")
    workflow.add_edge("understand", "supervisor")

    # Supervisor 路由
    workflow.add_conditional_edges(
        "supervisor",
        supervisor_route,
        {
            "generate_sql": "generate_sql",
            "greeting_response": "greeting_response",
            "help_response": "help_response",
            "end": END,
        }
    )

    # 数据查询流程
    workflow.add_edge("generate_sql", "execute_sql")
    workflow.add_edge("execute_sql", "postprocess")
    workflow.add_edge("postprocess", "summary")

    # 问候和帮助流程
    workflow.add_edge("greeting_response", "summary")
    workflow.add_edge("help_response", "summary")

    # Summary 结束
    workflow.add_edge("summary", END)

    return workflow.compile()


# 全局实例
conversation_graph = create_conversation_graph()
