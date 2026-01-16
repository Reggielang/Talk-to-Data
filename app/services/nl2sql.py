from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from loguru import logger
from config import get_settings
from app.db.mysql import mysql_client

settings = get_settings()


class NL2SQLService:
    """自然语言转 SQL 服务."""

    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4",
            temperature=0,
            openai_api_key=settings.openai_api_key,
        )
        self.schema = None

    def load_schema(self):
        """加载 MySQL schema."""
        if not self.schema:
            self.schema = mysql_client.get_schema()
        return self.schema

    def build_schema_prompt(self) -> str:
        """构建 schema 提示."""
        schema = self.load_schema()
        schema_text = "Available tables:\n\n"

        for table, columns in schema.items():
            schema_text += f"Table: {table}\n"
            schema_text += "Columns:\n"
            for col in columns:
                comment = f" - {col['comment']}" if col['comment'] else ""
                schema_text += f"  - {col['column']} ({col['type']}){comment}\n"
            schema_text += "\n"

        return schema_text

    def convert(self, query: str, session_context: Optional[list] = None) -> str:
        """将自然语言转换为 SQL."""
        schema_text = self.build_schema_prompt()

        context = ""
        if session_context:
            context = "\n\nPrevious conversation:\n"
            for item in session_context[-3:]:  # 只看最近3轮
                context += f"Q: {item['user_query']}\n"
                context += f"SQL: {item['generated_sql']}\n\n"

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a SQL expert. Convert natural language queries to MySQL SQL.

Rules:
1. Use proper JOIN syntax
2. Always include column names (no SELECT *)
3. Use appropriate WHERE clauses
4. Add LIMIT to prevent large result sets
5. Only output the SQL query, no explanation

{schema}"""),
            ("user", "{context}Question: {query}")
        ])

        chain = prompt | self.llm

        try:
            response = chain.invoke({
                "schema": schema_text,
                "context": context,
                "query": query
            })
            sql = response.content.strip()
            # 清理可能的 markdown 代码块标记
            if sql.startswith("```sql"):
                sql = sql[6:]
            elif sql.startswith("```"):
                sql = sql[3:]
            if sql.endswith("```"):
                sql = sql[:-3]
            return sql.strip()
        except Exception as e:
            logger.error(f"NL2SQL conversion error: {e}")
            raise


# 全局实例
nl2sql_service = NL2SQLService()
