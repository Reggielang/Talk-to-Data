"""Prompt 模板管理服务."""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template
from loguru import logger
from typing import Any

class PromptTemplateService:
    """Prompt 模板服务."""

    def __init__(self, template_dir: Path | str | None = None):
        """初始化模板服务.

        Args:
            template_dir: 模板目录路径，默认为 app/conf/prompt_template
        """
        if template_dir is None:
            # 默认模板目录
            template_dir = Path(__file__).parent.parent / "conf" / "prompt_template"

        self.template_dir = Path(template_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=False,  # 不需要 HTML 转义
        )

        logger.info(f"PromptTemplateService initialized with template dir: {self.template_dir}")

    def get_template(self, template_name: str) -> Template:
        """获取模板.
        Args:
            template_name: 模板文件名
        Returns:
            Jinja2 Template 对象
        """
        try:
            template = self.env.get_template(template_name)
            logger.debug(f"Loaded template: {template_name}")
            return template
        except Exception as e:
            logger.error(f"Failed to load template {template_name}: {e}")
            raise

    def render(self, template_name: str, **kwargs) -> str:
        """渲染模板.

        Args:
            template_name: 模板文件名
            **kwargs: 模板变量

        Returns:
            渲染后的字符串
        """
        template = self.get_template(template_name)
        result = template.render(**kwargs)
        logger.debug(f"Rendered template {template_name} with vars: {list(kwargs.keys())}")
        return result


# 全局实例
prompt_template_service = PromptTemplateService()


# 测试代码
if __name__ == "__main__":
    import sys
    import io

    # 设置 UTF-8 输出
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    prompt_config = PromptTemplateService()

    print("=" * 60)
    print("测试 block 模板")
    print("=" * 60)
    result_zh = prompt_config.render("block_user.j2")
    print(result_zh)
