"""DataQuery 节点 - 使用 LLM 生成 SQL 并执行查询."""

import re
from datetime import datetime
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from loguru import logger

from app.graph.core.state import State
from app.conf.prompt_init import PromptConfig
from app.conf.utils.prompt_parms import create_date_function
from app.services.llm_service import llm_service, LlmRequest




def capture_sql_blocks(content: str) -> list[str]:
    """从内容中提取 SQL 代码块."""
    pattern = r'```sql\s*(.*?)\s*```'
    matches = re.findall(pattern, content, re.DOTALL)
    if matches:
        return matches

    # 尝试匹配没有语言标识的代码块
    pattern = r'```\s*(.*?)\s*```'
    matches = re.findall(pattern, content, re.DOTALL)
    return matches


def execute_sql_query(sql: str) -> tuple[str, str, int]:
    """执行 SQL 查询（需要根据实际项目实现）.

    Args:
        sql: SQL 查询语句

    Returns:
        (json_content, sample_json_content, data_length)
    """
    # TODO: 实现实际的 SQL 查询逻辑
    # 这里需要连接到数据库执行查询
    # 例如使用 pymysql、sqlalchemy 等

    logger.info(f"Executing SQL: {sql}")

    # 临时返回空数据
    # 实际实现时需要:
    # 1. 连接数据库
    # 2. 执行查询
    # 3. 获取结果
    # 4. 返回 JSON 格式的内容和样本数据

    return "[]", "[]", 0


def data_query_node(state: State, task: str, table: str) -> State:
    """DataQuery 节点 - 使用 LLM 生成 SQL 并执行查询.

    Args:
        state: 对话状态
        task: 用户任务/问题
        table: 表名（可以是逗号分隔的多个表）

    Returns:
        更新后的 State
    """
    logger.info(f"DataQuery node: task={task}, table={table}")

    # 检查是否被拦截
    if state.get("IsBlocked", False):
        logger.info("Query is blocked, skipping DataQuery node.")
        return state

    try:
        # 1. 初始化配置
        prompt_config = PromptConfig()
        date_func = create_date_function(state.get("CurrentDatetime", datetime.now()))


        system_prompt = prompt_config.render(
            "data_query_system.j2",
            date=date_func,
            task=task,
        )

        # 3. 构建初始消息
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=task),
        ]

        logger.info(f"DataQuery System Prompt: {system_prompt[:200]}...")

        # 4. SQL 生成和验证循环
        max_iterations = 3
        max_success_iterations = 1
        current_iteration = 0
        success_iterations = 0

        continuous_empty_result_times = 0
        max_empty_result_times = 2
        same_result_times = 0
        same_result_threshold = 2
        history_query_results = []

        sql = ""
        query_result = ""
        query_result_sample = ""
        data_length = 0

        while current_iteration < max_iterations and success_iterations < max_success_iterations:
            current_iteration += 1

            # 生成 SQL
            request = LlmRequest(
                messages=messages,
                model_name=state.get("LlmModelName"),
                temperature=0.1,
            )

            assistant_content, _ = llm_service.simple_chat(request)
            logger.info(f"LLM response: {assistant_content}")

            # 检查是否需要修改
            if "我认为不需要修改" in assistant_content or "不需要修改" in assistant_content:
                break

            # 提取 SQL 代码块
            sqls = capture_sql_blocks(assistant_content)
            if len(sqls) == 0:
                messages.append(HumanMessage(content="必须使用```sql```格式输出SQL查询语句。请重新输出。"))
                continue

            if len(sqls) > 1:
                messages.append(HumanMessage(content="最多只允许输出一个SQL语句，请重新输出。"))
                continue

            sql = sqls[0]
            logger.info(f"Generated SQL: {sql}")

            # 添加助手消息到历史
            messages.append(AIMessage(content=assistant_content))

            # 执行 SQL 查询
            query_result, query_result_sample, data_length = execute_sql_query(sql)

            # 检查查询是否成功
            if data_length == 0:
                # 空结果处理
                if query_result in history_query_results:
                    continuous_empty_result_times += 1
                else:
                    continuous_empty_result_times = 0

                if continuous_empty_result_times >= max_empty_result_times:
                    break

                messages.append(HumanMessage(
                    content=f"查询结果为空。SQL: {sql}\n请检查并优化查询条件。"
                ))
            else:
                # 有结果
                if query_result in history_query_results:
                    same_result_times += 1
                    if same_result_times >= same_result_threshold:
                        break

                history_query_results.append(query_result)

            success_iterations += 1

            # 如果达到最大成功迭代次数，停止
            if success_iterations >= max_success_iterations:
                break

            # 继续优化
            messages.append(HumanMessage(
                content=f"查询成功。结果样本:\n```\n{query_result_sample}\n```\n"
                f"数据行数: {data_length}\n"
                f"如果结果满意，回复'我认为不需要修改'。否则请优化SQL。"
            ))

        # 5. 更新 State
        state["SqlGenResult"] = {
            "Sql": sql,
        }

        state["DataQueryResult"] = {
            "JsonContent": query_result,
            "SampleData": query_result_sample,
            "DataRowLength": data_length,
            "QueriedDataRowLength": data_length,
            "IsPartialData": False,
            "IsNeedPostProcess": False,
        }

        # 如果查询成功，可以生成最终回复
        if data_length > 0:
            state["Response"] = f"查询成功，共 {data_length} 条数据。\n\n结果:\n{query_result_sample[:500]}"
        else:
            state["Response"] = "查询已完成，但没有找到匹配的数据。"

        logger.info(f"DataQuery node completed. SQL: {sql[:100]}..., Rows: {data_length}")

    except Exception as e:
        logger.error(f"DataQuery node error: {e}")
        state["Response"] = f"查询过程中发生错误: {str(e)}"

    return state