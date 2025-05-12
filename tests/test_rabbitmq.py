import pytest
import time
import pika
from loguru import logger

@pytest.fixture(scope="function")
def rabbitmq_connection():
    """创建 RabbitMQ 连接实例"""
    connection = None
    max_retries = 5
    for attempt in range(max_retries):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host="localhost",
                    port=5672,
                    credentials=pika.PlainCredentials("guest", "guest"),
                    heartbeat=600
                )
            )
            return connection
        except Exception as e:
            logger.error(f"连接 RabbitMQ 失败 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                pytest.fail(f"连接 RabbitMQ 失败: {e}")
            time.sleep(2)  # 等待2秒后重试

def test_rabbitmq_connection(rabbitmq_connection):
    """测试 RabbitMQ 服务是否可以连接"""
    assert not rabbitmq_connection.is_closed, "RabbitMQ 连接失败"
    logger.info("成功连接到 RabbitMQ 服务")
    rabbitmq_connection.close()

def test_rabbitmq_queue_creation(rabbitmq_connection):
    """测试 RabbitMQ 是否可以创建队列"""
    queue_name = "test_queue"
    try:
        channel = rabbitmq_connection.channel()
        channel.queue_declare(queue=queue_name, durable=False)
        logger.info(f"成功创建队列: {queue_name}")
        
        # 检查队列是否存在
        queue_info = channel.queue_declare(queue=queue_name, passive=True)
        assert queue_info.method.queue == queue_name, f"队列 {queue_name} 未创建成功"
    except Exception as e:
        logger.error(f"创建 RabbitMQ 队列失败: {e}")
        pytest.fail(f"创建 RabbitMQ 队列失败: {e}")
    finally:
        # 清理测试数据
        if not rabbitmq_connection.is_closed:
            channel = rabbitmq_connection.channel()
            channel.queue_delete(queue=queue_name)
            rabbitmq_connection.close()