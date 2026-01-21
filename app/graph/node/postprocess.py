"""PostProcess 节点 - 对数据集进行加工和算法操作.

参考 Go 版本实现，通过 LLM 生成 Python 代码并执行来处理数据。
"""

import json
import re
import subprocess
import sys
from datetime import datetime
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from app.graph.core.state import State
from app.conf.prompt_init import PromptConfig
from app.conf.utils.prompt_parms import create_date_function
from app.services.llm_service import llm_service, LlmRequest


# Python 代码块提取正则
PYTHON_CODE_BLOCK_PATTERN = re.compile(r'```python\n(.*?)\n```', re.DOTALL)


def extract_python_blocks(content: str) -> list[str]:
    """从内容中提取 Python 代码块"""
    matches = PYTHON_CODE_BLOCK_PATTERN.findall(content)
    return matches


def execute_python_code(code: str, datasets: dict) -> tuple[str, bool]:
    """执行 Python 代码

    Args:
        code: Python 代码
        datasets: 数据集字典，会作为 dataset1, dataset2 等变量传入

    Returns:
        (执行结果/错误信息, 是否失败)
    """
    # 准备数据集变量
    dataset_vars = {}
    for ds_id, dataset in datasets.items():
        # 将数据集内容转换为 Python 可用的格式
        dataset_vars[f"dataset{ds_id}"] = dataset.get("Content", "")

    # 构建完整的 Python 代码
    full_code = ""
    for var_name, data in dataset_vars.items():
        full_code += f"{var_name} = {json.dumps(data, ensure_ascii=False)}\n"

    full_code += f"""
                    import json
                    import pandas as pd
                    import numpy as np
                    from io import StringIO

                    # 结果输出函数
                    def set_result(result):
                        print(f"__RESULT__:{{json.dumps(result, ensure_ascii=False)}}")

                    # 执行用户代码
                    {code}
"""

    try:
        # 使用 subprocess 调用 Python
        result = subprocess.run(
            [sys.executable, "-c", full_code],
            capture_output=True,
            text=True,
            timeout=30  # 30秒超时
        )

        # 检查是否有结果输出
        output = result.stdout
        error = result.stderr

        if result.returncode != 0:
            return error or "执行失败", True

        # 提取结果
        if "__RESULT__:" in output:
            # 提取结果 JSON
            result_match = re.search(r'__RESULT__:(.+)', output)
            if result_match:
                try:
                    result_json = json.loads(result_match.group(1))
                    return json.dumps(result_json, ensure_ascii=False), False
                except:
                    return result_match.group(1), False

        # 如果没有特殊结果输出，返回所有输出
        return output or "执行成功，无输出", False

    except subprocess.TimeoutExpired:
        return "Python 代码执行超时（30秒）", True
    except Exception as e:
        return f"执行异常: {str(e)}", True


def postprocess_node(state: State) -> State:
    """PostProcess 节点 - 对数据集进行加工和算法操作.

    Args:
        state: 对话状态

    Returns:
        更新后的 State
    """
    # 检查是否被拦截
    if state.get("IsBlocked", False):
        logger.info("Query is blocked, skipping PostProcess node.")
        return state

    # 设置 state 到 llm_service，自动记录 LLM 调用
    llm_service.set_state(state)

    try:
        task = state.get("PostProcessTask", "")
        dataset_ids_str = state.get("PostProcessDatasetId", "")

        logger.info(f"PostProcess task: {task}, dataset_ids: {dataset_ids_str}")

        # 解析数据集 ID
        dataset_ids = [d.strip() for d in dataset_ids_str.split(",") if d.strip()]
        datasets = state.get("Datasets", {})

        # 检查数据集是否存在
        valid_dataset_ids = []
        dataset_samples = []
        for ds_id in dataset_ids:
            if ds_id in datasets:
                valid_dataset_ids.append(ds_id)
                dataset = datasets[ds_id]
                # 构建数据集样例信息
                sample_info = f"## 数据集ID: {ds_id}\n"
                if dataset.get("ErrorText"):
                    sample_info += f"数据集存在错误和数据缺失: {dataset['ErrorText']}\n"
                sample_info += f"### 样例数据\n```json\n{dataset.get('SampleData', '')}\n```\n"
                dataset_samples.append(sample_info)
            else:
                logger.warning(f"Dataset {ds_id} not found")

        if not valid_dataset_ids:
            state["PostProcessResult"] = {
                "HasError": True,
                "Result": f"没有找到有效的数据集: {dataset_ids_str}"
            }
            state["PostProcessTask"] = ""
            state["PostProcessDatasetId"] = ""
            return state

        # 初始化配置
        prompt_config = PromptConfig()
        date_func = create_date_function(state.get("CurrentDatetime", datetime.now()))

        # 构建用户提示
        user_prompt = "\n\n---\n\n".join(dataset_samples)
        user_prompt += f"\n\n允许使用的数据集ID: [{','.join(valid_dataset_ids)}]\n"
        user_prompt += f"\n任务: {task}"

        # 构建系统提示
        system_prompt = prompt_config.render(
            "post_process_system.j2",
            date=date_func
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        # 生成 Python 代码（支持 self-refine）
        max_iterations = 3
        max_success_iterations = max(state.get("PostprocessRethinkTimes", 0) + 1, 1)
        current_iteration = 0
        success_iterations = 0

        final_code = ""
        execute_result = ""
        execute_failed = False

        # 准备执行用的数据集
        exec_datasets = {ds_id: datasets[ds_id] for ds_id in valid_dataset_ids}

        while current_iteration < max_iterations and success_iterations < max_success_iterations:
            current_iteration += 1

            # 调用 LLM 生成代码
            request = LlmRequest(
                messages=messages,
                model_name=state.get("LlmModelName"),
                temperature=0.1,
            )
            response = llm_service.simple_chat(request)

            # 检查是否需要继续
            if "我认为不需要修改" in response:
                break

            # 提取 Python 代码
            codes = extract_python_blocks(response)
            if not codes:
                messages.append(HumanMessage(content="必须使用```python```格式输出代码。请重新输出。"))
                continue
            if len(codes) > 1:
                messages.append(HumanMessage(content="最多只允许输出一个Python代码块，请重新输出。"))
                continue

            code = codes[0]
            final_code = code

            logger.info(f"Executing Python code:\n{code[:200]}...")

            # 执行 Python 代码
            execute_result, execute_failed = execute_python_code(code, exec_datasets)

            if execute_failed:
                messages.append(HumanMessage(
                    content=f"执行Python代码失败，检查并修复代码并重新输出。错误信息：\n```\n{execute_result}\n```"
                ))
                continue

            # 执行成功
            last_chance = success_iterations == max_success_iterations - 1
            success_iterations += 1

            if success_iterations >= max_success_iterations:
                break

            # 添加一致性检查提示
            consistency_prompt = prompt_config.render(
                "post_process_user.j2",
                ExecuteResult=execute_result,
                LastChance=last_chance
            )
            messages.append(HumanMessage(content=consistency_prompt))

        # 保存结果
        state["PostProcessResult"] = {
            "HasError": execute_failed,
            "Result": execute_result,
            "GeneratedCode": final_code,
        }

        # 清除任务
        state["PostProcessTask"] = ""
        state["PostProcessDatasetId"] = ""

        logger.info("PostProcess node completed")

    except Exception as e:
        logger.error(f"PostProcess node error: {e}")
        state["PostProcessResult"] = {
            "HasError": True,
            "Result": str(e)
        }
        state["PostProcessTask"] = ""
        state["PostProcessDatasetId"] = ""

    return state