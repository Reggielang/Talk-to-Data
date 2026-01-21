# import redis
# import json
# from typing import Optional, Any, Dict
# from loguru import logger
# from app.conf.config import settings

# class RedisClient:
#     """Redis 客户端 - 用于缓存和会话管理."""

#     def __init__(self):
#         self.client = redis.Redis(
#             host=settings.redis_host,
#             port=settings.redis_port,
#             password=settings.redis_password if settings.redis_password else None,
#             db=settings.redis_db,
#             decode_responses=True,
#         )

#     def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
#         """设置键值."""
#         try:
#             if isinstance(value, (dict, list)):
#                 value = json.dumps(value)
#             return self.client.setex(key, ttl or settings.session_ttl, value)
#         except Exception as e:
#             logger.error(f"Redis set error: {e}")
#             return False

#     def get(self, key: str) -> Optional[Any]:
#         """获取值."""
#         try:
#             value = self.client.get(key)
#             if value:
#                 try:
#                     return json.loads(value)
#                 except json.JSONDecodeError:
#                     return value
#             return None
#         except Exception as e:
#             logger.error(f"Redis get error: {e}")
#             return None

#     def delete(self, key: str) -> bool:
#         """删除键."""
#         try:
#             return bool(self.client.delete(key))
#         except Exception as e:
#             logger.error(f"Redis delete error: {e}")
#             return False

#     def exists(self, key: str) -> bool:
#         """检查键是否存在."""
#         try:
#             return bool(self.client.exists(key))
#         except Exception as e:
#             logger.error(f"Redis exists error: {e}")
#             return False

#     # 会话管理
#     def save_session_state(self, session_id: str, state: Dict[str, Any]) -> bool:
#         """保存会话状态."""
#         key = f"session:{session_id}"
#         return self.set(key, state, settings.session_ttl)

#     def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
#         """获取会话状态."""
#         key = f"session:{session_id}"
#         return self.get(key)

#     def clear_session(self, session_id: str) -> bool:
#         """清除会话."""
#         key = f"session:{session_id}"
#         return self.delete(key)

#     # 查询缓存
#     def cache_query_result(self, query_hash: str, result: Any, ttl: int = 3600) -> bool:
#         """缓存查询结果."""
#         key = f"query_cache:{query_hash}"
#         return self.set(key, result, ttl)

#     def get_cached_query(self, query_hash: str) -> Optional[Any]:
#         """获取缓存的查询结果."""
#         key = f"query_cache:{query_hash}"
#         return self.get(key)


# # 全局实例
# redis_client = RedisClient()
