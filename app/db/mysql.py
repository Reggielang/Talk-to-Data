import pymysql
from pymysql.converters import conversions
from decimal import Decimal
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from loguru import logger
from app.conf.config import settings
import threading


class MySQLClient:
    """MySQL 客户端（连接池版本）."""
    
    _local = threading.local()  # 线程本地存储
    _pool = []  # 连接池
    _max_pool_size = 10
    _lock = threading.Lock()

    def __init__(self):
        # 配置 Decimal 转换为 float
        conv = conversions.copy()
        conv[Decimal] = float

        self.config = {
            "host": settings.mysql_host,
            "port": settings.mysql_port,
            "user": settings.mysql_user,
            "password": settings.mysql_password,
            "database": settings.mysql_database,
            "charset": "utf8mb4",
            "cursorclass": pymysql.cursors.DictCursor,
            "conv": conv,
            "autocommit": False,  # 手动控制事务
        }

    def _get_connection_from_pool(self):
        """从连接池获取连接."""
        with self._lock:
            if self._pool:
                return self._pool.pop()
        
        # 创建新连接
        return pymysql.connect(**self.config)

    def _return_connection_to_pool(self, conn):
        """将连接放回连接池."""
        with self._lock:
            if len(self._pool) < self._max_pool_size:
                self._pool.append(conn)
            else:
                conn.close()

    @contextmanager
    def get_connection(self):
        """获取数据库连接（连接池版本）."""
        conn = self._get_connection_from_pool()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()  # 自动提交
        finally:
            self._return_connection_to_pool(conn)

    def execute_query(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """执行查询（优化版本）."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 使用 executemany 批量查询（如果有多个参数）
                    if params is not None:
                        cursor.execute(sql, params)
                    else:
                        cursor.execute(sql)
                    
                    # 分批获取结果，减少内存占用
                    batch_size = 1000
                    result = []
                    while True:
                        rows = cursor.fetchmany(batch_size)
                        if not rows:
                            break
                        result.extend(rows)
                        
                        # 如果结果超过最大限制，提前结束
                        if len(result) >= settings.max_query_results:
                            break
                    
                    return result[:settings.max_query_results]  # 确保不超过限制
        except Exception as e:
            logger.error(f"MySQL query error: {e}")
            raise


# 全局实例
mysql_client = MySQLClient()