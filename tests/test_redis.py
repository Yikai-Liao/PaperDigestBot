import pytest
import redis
from loguru import logger

@pytest.fixture
def redis_client():
    """创建 Redis 客户端实例"""
    client = redis.Redis(host="localhost", port=6379, decode_responses=True)
    return client

def test_redis_connection(redis_client):
    """测试 Redis 服务是否可以连接"""
    try:
        # 尝试 ping Redis 服务
        response = redis_client.ping()
        logger.info("成功连接到 Redis 服务")
        assert response is True, "Redis 服务未响应"
    except redis.ConnectionError as e:
        logger.error(f"连接 Redis 服务失败: {e}")
        pytest.fail(f"连接 Redis 服务失败: {e}")

def test_redis_set_get(redis_client):
    """测试 Redis 是否可以设置和获取值"""
    test_key = "test_key"
    test_value = "test_value"
    try:
        # 设置值
        redis_client.set(test_key, test_value)
        logger.info(f"成功设置键值对: {test_key} = {test_value}")
        
        # 获取值
        retrieved_value = redis_client.get(test_key)
        assert retrieved_value == test_value, f"获取的值不匹配，期望 {test_value}，实际 {retrieved_value}"
        logger.info(f"成功获取值: {retrieved_value}")
    except redis.RedisError as e:
        logger.error(f"Redis 操作失败: {e}")
        pytest.fail(f"Redis 操作失败: {e}")
    finally:
        # 清理测试数据
        redis_client.delete(test_key)