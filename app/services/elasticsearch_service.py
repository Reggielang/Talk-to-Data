"""Elasticsearch 服务 - 用于 Few-Shot SQL 示例检索."""

from typing import List, Optional
from loguru import logger
from app.conf.config import settings

try:
    from elasticsearch import Elasticsearch
except ImportError:
    Elasticsearch = None
    logger.warning("elasticsearch package not installed. Install with: pip install elasticsearch")


class ElasticsearchService:
    """Elasticsearch 服务 - 检索相似的 Few-Shot SQL 示例."""

    def __init__(self):
        """初始化 Elasticsearch 客户端."""
        if Elasticsearch is None:
            self.client = None
            logger.warning("Elasticsearch client not available")
            return

        try:
            # 构建 Elasticsearch 连接 URL
            if settings.es_user and settings.es_password:
                self.client = Elasticsearch(
                    [f"{settings.es_scheme}://{settings.es_host}:{settings.es_port}"],
                    basic_auth=(settings.es_user, settings.es_password),
                    verify_certs=False,
                    ssl_show_warn=False,
                )
            else:
                self.client = Elasticsearch(
                    [f"{settings.es_scheme}://{settings.es_host}:{settings.es_port}"],
                    verify_certs=False,
                    ssl_show_warn=False,
                )

            # 测试连接
            if self.client.ping():
                logger.info(f"✅ Elasticsearch connected: {settings.es_host}:{settings.es_port}")
            else:
                logger.warning(f"⚠️ Elasticsearch connection failed: {settings.es_host}:{settings.es_port}")
                self.client = None

        except Exception as e:
            logger.error(f"❌ Elasticsearch connection error: {e}")
            self.client = None

    def search_fewshot_sql(
        self,
        query_text: str,
        top_k: int = 3,
        min_score: float = 0.5,
    ) -> List[dict]:
        """基于语义搜索检索相似的 Few-Shot SQL 示例.

        Args:
            query_text: 用户查询文本
            top_k: 返回前 K 个结果
            min_score: 最小相似度分数阈值

        Returns:
            Few-Shot SQL 示例列表，每个包含:
            - question: 原始问题
            - sql: SQL 语句
            - score: 相似度分数
        """
        if self.client is None:
            logger.warning("Elasticsearch client not available, returning empty results")
            return []

        try:
            # 使用语义搜索（text_similarity 或稠密向量检索）
            # 这里使用简单的 text_similarity (BM25)，如果有向量模型可以使用 knn 搜索
            search_body = {
                "query": {
                    "bool": {
                        "should": [
                            {
                                "match": {
                                    "EmbeddingText": {
                                        "query": query_text,
                                        "boost": 2.0,  # EmbeddingText 权重更高
                                    }
                                }
                            },
                            {
                                "match": {
                                    "Question": {
                                        "query": query_text,
                                        "boost": 1.0,
                                    }
                                }
                            },
                        ],
                        "minimum_should_match": 1,
                    }
                },
                "size": top_k,
                "min_score": min_score,
            }

            response = self.client.search(
                index=settings.es_index,
                body=search_body,
            )

            fewshot_examples = []
            for hit in response.get("hits", {}).get("hits", []):
                source = hit.get("_source", {})
                score = hit.get("_score", 0)

                # 解析 Content 字段（JSON 字符串）
                content_str = source.get("Content", "{}")
                try:
                    import json
                    content_data = json.loads(content_str)
                    sql = content_data.get("Sql", "")
                except:
                    sql = ""

                question = source.get("Question", source.get("EmbeddingText", ""))

                fewshot_examples.append({
                    "question": question,
                    "sql": sql,
                    "score": score,
                })

            logger.info(f"Retrieved {len(fewshot_examples)} few-shot examples from ES")
            return fewshot_examples

        except Exception as e:
            logger.error(f"Elasticsearch search error: {e}")
            return []

    def format_fewshot_examples(self, examples: List[dict]) -> str:
        """将 Few-Shot 示例格式化为 Prompt 字符串.

        Args:
            examples: Few-Shot 示例列表

        Returns:
            格式化的 Few-Shot Prompt 字符串
        """
        if not examples:
            return ""

        formatted_lines = []
        formatted_lines.append("\n### 参考示例 (Few-Shot Examples)\n")

        for i, example in enumerate(examples, 1):
            question = example.get("question", "")
            sql = example.get("sql", "")
            score = example.get("score", 0)

            # 清理 SQL 中的多余注释和格式
            sql = self._clean_sql(sql)

            formatted_lines.append(f"#### 示例 {i} (相似度: {score:.2f})")
            formatted_lines.append(f"**问题:** {question}")
            formatted_lines.append(f"**SQL:**")
            formatted_lines.append("```sql")
            formatted_lines.append(sql)
            formatted_lines.append("```")
            formatted_lines.append("")

        return "\n".join(formatted_lines)

    def _clean_sql(self, sql: str) -> str:
        """清理 SQL 语句，移除过长的注释。

        Args:
            sql: 原始 SQL

        Returns:
            清理后的 SQL
        """
        if not sql:
            return sql

        # 移除 /*...*/ 风格的多行注释（保留简短注释）
        import re

        # 如果注释超过 100 字符，移除
        def replace_long_comment(match):
            comment = match.group(0)
            if len(comment) > 150:
                return ""
            return comment

        # 替换块注释
        sql = re.sub(r'/\*.*?\*/', replace_long_comment, sql, flags=re.DOTALL)

        # 移除行末注释（但保留简短注释）
        sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)

        # 清理多余空行
        sql = re.sub(r'\n\s*\n', '\n', sql)

        return sql.strip()


# 全局单例
elasticsearch_service = ElasticsearchService()
