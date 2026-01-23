"""DataQuery 节点 - 使用 LLM 生成 SQL 并执行查询."""

import json
import re
from datetime import datetime
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from app.graph.core.state import State
from app.conf.prompt_init import PromptConfig
from app.conf.utils.prompt_parms import create_date_function
from app.services.llm_service import llm_service, LlmRequest
from app.db.mysql import mysql_client
from decimal import Decimal


# SQL 代码块提取正则
SQL_BLOCK_PATTERN = re.compile(r'```sql\s*(.*?)\s*```', re.DOTALL)
CODE_BLOCK_PATTERN = re.compile(r'```\s*(.*?)\s*```', re.DOTALL)


def capture_sql_blocks(content: str) -> list[str]:
    """从内容中提取 SQL 代码块."""
    matches = SQL_BLOCK_PATTERN.findall(content)
    if matches:
        return matches
    matches = CODE_BLOCK_PATTERN.findall(content)
    return matches


def execute_sql_query(sql: str) -> tuple[str, str, int]:
    """执行 SQL 查询."""
    logger.info(f"Executing SQL: {sql}")
    try:
        results = mysql_client.execute_query(sql)
        data_length = len(results)
        if data_length == 0:
            return "[]", "[]", 0

        def decimal_default(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            raise TypeError(f"Type {type(obj)} not serializable")

        json_content = json.dumps(results, default=decimal_default, ensure_ascii=False)
        sample_size = min(5, len(results))
        sample_data = results[:sample_size]
        sample_json_content = json.dumps(sample_data, default=decimal_default, indent=2, ensure_ascii=False)
        return json_content, sample_json_content, data_length
    except Exception as e:
        logger.error(f"Error executing SQL: {e}")
        raise


def data_query_node(state: State) -> State:
    """DataQuery 节点 - 使用 LLM 生成 SQL 并执行查询."""
    if state.get("IsBlocked", False):
        return state

    llm_service.set_state(state)

    try:
        task = state.get("DataQueryTask", "")
        table = state.get("DataQueryTable", "")
        logger.info(f"DataQuery task: {task}, table: {table}")

        prompt_config = PromptConfig()
        date_func = create_date_function(state.get("CurrentDatetime", datetime.now()))

        system_prompt = prompt_config.render(
            "data_query_system.j2",
            date=date_func,
            table=table,
            task=task,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=task),
        ]

        # Self-refine 循环
        max_iterations = 3
        max_success_iterations = max(state.get("DataQueryRethinkTimes", 0) + 1, 1)
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

            request = LlmRequest(
                messages=messages,
                model_name=state.get("LlmModelName"),
                temperature=0.1,
            )
            assistant_content = llm_service.simple_chat(request)

            if "我认为不需要修改" in assistant_content:
                break

            sqls = capture_sql_blocks(assistant_content)
            if len(sqls) == 0:
                messages.append(HumanMessage(content="必须使用```sql```格式输出SQL查询语句。请重新输出。"))
                continue

            if len(sqls) > 1:
                messages.append(HumanMessage(content="最多只允许输出一个SQL语句，请重新输出。"))
                continue

            sql = sqls[0]
            logger.info(f"Generated SQL: {sql}")

            prev_query_result = query_result
            query_result, query_result_sample, data_length = execute_sql_query(sql)

            # 空结果处理
            if data_length == 0:
                if prev_query_result == query_result:
                    continuous_empty_result_times += 1
                else:
                    continuous_empty_result_times = 0
                if continuous_empty_result_times >= max_empty_result_times:
                    break
                messages.append(HumanMessage(content=f"查询结果为空。SQL: {sql}\n请检查并优化查询条件。"))
                continue

            # 有结果
            if query_result in history_query_results:
                same_result_times += 1
                if same_result_times >= same_result_threshold:
                    break
            history_query_results.append(query_result)
            success_iterations += 1

            if success_iterations >= max_success_iterations:
                break

            # 继续优化
            last_chance = success_iterations == max_success_iterations - 1
            consistency_prompt = prompt_config.render(
                "data_query_consistency_user.j2",
                queryresult=query_result_sample,
                lastchance=last_chance,
                morethansampledata=data_length > 5,
                sampledatalength=5,
                queryresultlength=data_length,
                task=task,
            )
            messages.append(HumanMessage(content=consistency_prompt))

        # 更新 State
        state["SqlGenResult"] = {"Sql": sql}
        state["DataQueryResult"] = {
            "JsonContent": query_result,
            "SampleData": query_result_sample,
            "DataRowLength": data_length,
            "QueriedDataRowLength": data_length,
            "IsPartialData": data_length > 50,
        }

        # 保存数据集
        dataset_id = str(len(state.get("Datasets", {})) + 1)
        state["Datasets"][dataset_id] = {
            "Task": task,
            "Table": table,
            "Content": query_result,
            "SampleData": query_result_sample,
            "DataRowLength": data_length,
            "Sql": sql,
        }

        # 清除任务
        state["DataQueryTask"] = ""
        state["DataQueryTable"] = ""

        logger.info(f"DataQuery node completed. Rows: {data_length}")

    except Exception as e:
        logger.error(f"DataQuery node error: {e}")

    return state
