"""Elasticsearch 服务 - 用于 Few-Shot SQL 示例检索."""

from typing import List, Optional, Dict, Any
from loguru import logger
from app.conf.config import settings
from openai import OpenAI

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
            # 构建 Elasticsearch 连接
            if settings.es_user and settings.es_password:
                self.client = Elasticsearch(
                    [f"{settings.es_scheme}://{settings.es_host}:{settings.es_port}"],
                    basic_auth=(settings.es_user, settings.es_password),
                    verify_certs=False,
                    ssl_show_warn=False,
                    request_timeout=30,
                )
            else:
                self.client = Elasticsearch(
                    [f"{settings.es_scheme}://{settings.es_host}:{settings.es_port}"],
                    request_timeout=30,
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

    # ==================== 搜索方法 ====================

    def search_hybrid(
        self,
        query_text: str,
        index_name: str,
        top_k: int = 5,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> List[dict]:
        """混合搜索：向量搜索 + 关键词搜索.

        Args:
            query_text: 用户查询文本
            index_name: 索引名称
            top_k: 返回前 K 个结果
            vector_weight: 向量搜索权重 (0-1)
            keyword_weight: 关键词搜索权重 (0-1)

        Returns:
            搜索结果列表
        """
        if self.client is None:
            logger.warning("Elasticsearch client not available")
            return []

        try:
            # 获取查询向量
            query_vector = self.get_embedding(query_text)
            if not query_vector:
                logger.warning("Failed to get query vector, falling back to keyword search only")
                return self._search_keyword_only(query_text, index_name, top_k)

            # 混合搜索
            search_body = {
                "query": {
                    "bool": {
                        "should": [
                            # 向量搜索
                            {
                                "knn": {
                                    "field": "question_vector",
                                    "query_vector": query_vector,
                                    "k": top_k,
                                    "num_candidates": min(top_k * 10, 100),
                                    "boost": vector_weight,
                                }
                            },
                            # 关键词搜索
                            {
                                "match": {
                                    "question": {
                                        "query": query_text,
                                        "boost": keyword_weight,
                                    }
                                }
                            },
                        ],
                    }
                },
                "size": top_k,
            }

            response = self.client.search(index=index_name, body=search_body)

            results = []
            for hit in response.get("hits", {}).get("hits", []):
                source = hit.get("_source", {})
                score = hit.get("_score", 0)
                results.append({
                    "id": source.get("id"),
                    "question": source.get("question"),
                    "content": source.get("content"),
                    "score": score,
                })

            logger.info(f"✅ Hybrid search: {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"❌ Hybrid search error: {e}")
            return []

    def _search_keyword_only(
        self,
        query_text: str,
        index_name: str,
        top_k: int = 5,
    ) -> List[dict]:
        """纯关键词搜索（降级方案）.

        Args:
            query_text: 查询文本
            index_name: 索引名称
            top_k: 返回结果数

        Returns:
            搜索结果列表
        """
        if self.client is None:
            logger.warning("Elasticsearch client not available")
            return []

        try:
            search_body = {
                "query": {
                    "match": {
                        "question": query_text,
                    }
                },
                "size": top_k,
            }

            response = self.client.search(index=index_name, body=search_body)

            results = []
            for hit in response.get("hits", {}).get("hits", []):
                source = hit.get("_source", {})
                score = hit.get("_score", 0)
                results.append({
                    "id": source.get("id"),
                    "question": source.get("question"),
                    "content": source.get("content"),
                    "score": score,
                })

            return results

        except Exception as e:
            logger.error(f"❌ Keyword search error: {e}")
            return []

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

    # ==================== Embedding 方法 ====================

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """获取文本的向量表示.

        Args:
            text: 输入文本

        Returns:
            向量列表，失败返回 None
        """
        if OpenAI is None:
            logger.error("OpenAI package not installed")
            return None

        try:
            client = OpenAI(
                api_key=settings.qwen_api_key,
                base_url=settings.qwen_base_url,
            )

            response = client.embeddings.create(
                model="text-embedding-v4",
                input=text,
                dimensions=1024,
                encoding_format="float"
            )

            return response.data[0].embedding

        except Exception as e:
            logger.error(f"❌ Get embedding error: {e}")
            return None

    # ==================== 索引管理方法 ====================

    def create_index(
        self,
        index_name: str,
    ) -> Dict[str, Any]:
        """创建 Elasticsearch 索引.

        Args:
            index_name: 索引名称

        Returns:
            操作结果，包含 success 状态和详细信息
        """
        if self.client is None:
            return {"success": False, "error": "Elasticsearch client not available"}

        try:
            if self.client.indices.exists(index=index_name):
                return {"success": False, "error": f"Index '{index_name}' already exists"}

            body = {
                "mappings": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "question": {"type": "text"},
                        "content": {"type": "text"},
                        "question_vector": {
                            "type": "dense_vector",
                            "dims": 1024,
                            "index": True,
                            "similarity": "cosine"
                        },
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 1,
                }
            }

            response = self.client.indices.create(index=index_name, body=body)
            logger.info(f"✅ Index created: {index_name}")
            return {"success": True, "index": index_name, "response": response}

        except Exception as e:
            logger.error(f"❌ Create index error: {e}")
            return {"success": False, "error": str(e)}

    def delete_index(self, index_name: str) -> Dict[str, Any]:
        """删除 Elasticsearch 索引.

        Args:
            index_name: 索引名称

        Returns:
            操作结果
        """
        if self.client is None:
            return {"success": False, "error": "Elasticsearch client not available"}

        try:
            if not self.client.indices.exists(index=index_name):
                return {"success": False, "error": f"Index '{index_name}' does not exist"}

            response = self.client.indices.delete(index=index_name)
            logger.info(f"✅ Index deleted: {index_name}")
            return {"success": True, "index": index_name, "response": response}

        except Exception as e:
            logger.error(f"❌ Delete index error: {e}")
            return {"success": False, "error": str(e)}

    def index_exists(self, index_name: str) -> Dict[str, Any]:
        """检查索引是否存在.

        Args:
            index_name: 索引名称

        Returns:
            操作结果，包含 exists 状态
        """
        if self.client is None:
            return {"success": False, "exists": False, "error": "Elasticsearch client not available"}

        try:
            exists = self.client.indices.exists(index=index_name)
            return {"success": True, "exists": exists, "index": index_name}

        except Exception as e:
            logger.error(f"❌ Check index exists error: {e}")
            return {"success": False, "exists": False, "error": str(e)}

    def get_index_info(self, index_name: str) -> Dict[str, Any]:
        """获取索引详细信息.

        Args:
            index_name: 索引名称

        Returns:
            索引详细信息
        """
        if self.client is None:
            return {"success": False, "error": "Elasticsearch client not available"}

        try:
            if not self.client.indices.exists(index=index_name):
                return {"success": False, "error": f"Index '{index_name}' does not exist"}

            settings = self.client.indices.get_settings(index=index_name)
            mappings = self.client.indices.get_mapping(index=index_name)
            stats = self.client.indices.stats(index=index_name)

            return {
                "success": True,
                "index": index_name,
                "settings": settings.get(index_name, {}).get("settings", {}),
                "mappings": mappings.get(index_name, {}).get("mappings", {}),
                "stats": stats.get("indices", {}).get(index_name, {})
            }

        except Exception as e:
            logger.error(f"❌ Get index info error: {e}")
            return {"success": False, "error": str(e)}

    def add_document(
        self,
        index_name: str,
        document: Dict[str, Any],
        auto_embedding: bool = True,
    ) -> Dict[str, Any]:
        """添加文档到索引.

        Args:
            index_name: 索引名称
            document: 文档内容，包含 id, question, content
            auto_embedding: 是否自动获取 content 的向量

        Returns:
            操作结果
        """
        if self.client is None:
            return {"success": False, "error": "Elasticsearch client not available"}

        try:
            # 自动获取向量（基于 question 字段）
            if auto_embedding and "question" in document:
                question = document.get("question", "")
                if question:
                    vector = self.get_embedding(question)
                    if vector:
                        document["question_vector"] = vector
                        logger.info(f"✅ Got embedding for question (dim={len(vector)})")
                    else:
                        logger.warning(f"⚠️ Failed to get embedding, storing without vector")

            doc_id = document.get("id")
            if doc_id:
                response = self.client.index(index=index_name, id=doc_id, body=document)
            else:
                response = self.client.index(index=index_name, body=document)

            logger.info(f"✅ Document added to '{index_name}': {response.get('_id', '')}")
            return {
                "success": True,
                "index": index_name,
                "doc_id": response.get("_id", ""),
                "result": response.get("result", "")
            }

        except Exception as e:
            logger.error(f"❌ Add document error: {e}")
            return {"success": False, "error": str(e)}


# 全局单例
elasticsearch_service = ElasticsearchService()
