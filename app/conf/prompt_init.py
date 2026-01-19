"""Prompt 模板管理服务."""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template
from loguru import logger
from typing import Any
from app.conf.utils.prompt_parms import create_date_function
import os
import datetime
from dateutil.relativedelta import relativedelta

class PromptConfig:
    def __init__(self, base_date=None):
        # 模板目录
        self.template_dir = os.path.join(os.path.dirname(__file__), "prompt_template")
        
        # 创建Jinja2环境，指定编码为UTF-8
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir, encoding='utf-8'),
            autoescape=False
        )
        
    def render(self, template_name, **kwargs):
        """渲染模板"""
        try:
            template = self.env.get_template(template_name)
            return template.render(**kwargs)
        except Exception as e:
            print(f"渲染模板失败: {e}")
            raise


# # 全局实例
# prompt_template_service = PromptTemplateService()


# 测试代码
if __name__ == "__main__":
    import sys
    import io

    # 设置 UTF-8 输出
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    prompt_config = PromptConfig()
    date_func = create_date_function()

    print("=" * 60)
    print("测试 block 模板")
    print("=" * 60)

    result_zh = prompt_config.render("data_query_system.j2", date=date_func, task="请帮我查询在我的团队中哪个MR的销量最高？")
    logger.info("Rendered Prompt Template:\n" + result_zh)
