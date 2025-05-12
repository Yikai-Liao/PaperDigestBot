import pytest
import time
from qdrant_client import QdrantClient
from loguru import logger
import os
import requests

@pytest.fixture
def qdrant_client():
    """创建 Qdrant 客户端实例"""
    # 尝试多种可能的连接地址
    # 在 Podman 环境中，主机名 "localhost" 可能不正确
    # 对于 Podman，我们可能需要使用容器名或 IP 地址
    hosts = ["localhost", "127.0.0.1", "qdrant"]
    client = None
    
    # 保存原始代理设置
    original_http_proxy = os.environ.get('http_proxy')
    original_https_proxy = os.environ.get('https_proxy')
    original_all_proxy = os.environ.get('all_proxy')
    
    try:
        # 临时清除代理设置
        if 'http_proxy' in os.environ:
            del os.environ['http_proxy']
        if 'https_proxy' in os.environ:
            del os.environ['https_proxy']
        if 'all_proxy' in os.environ:
            del os.environ['all_proxy']
        
        # 创建一个不使用代理的会话
        session = requests.Session()
        session.trust_env = False  # 不使用环境变量中的代理
        
        for host in hosts:
            try:
                logger.info(f"尝试连接到 Qdrant 服务: {host}:6333")
                # 使用自定义会话并明确禁用代理
                client = QdrantClient(
                    host=host, 
                    port=6333, 
                    check_compatibility=False, 
                    timeout=10.0,
                    prefer_grpc=False,  # 使用HTTP而不是gRPC
                    https=False,        # 使用HTTP而不是HTTPS
                    # requests_session=session  # 使用不信任环境代理的会话
                )
                # 测试连接是否有效
                client.get_collections()
                logger.info(f"成功连接到 Qdrant 服务: {host}:6333")
                return client
            except Exception as e:
                logger.warning(f"连接到 {host}:6333 失败: {str(e)}")
        
        # 如果所有尝试都失败，返回最后一个客户端实例
        # pytest 会在测试中报告具体错误
        return QdrantClient(
            host="localhost", 
            port=6333, 
            check_compatibility=False, 
            timeout=10.0,
            prefer_grpc=False,
            https=False
        )
    finally:
        # 恢复原始代理设置
        if original_http_proxy:
            os.environ['http_proxy'] = original_http_proxy
        if original_https_proxy:
            os.environ['https_proxy'] = original_https_proxy
        if original_all_proxy:
            os.environ['all_proxy'] = original_all_proxy

def test_qdrant_connection(qdrant_client):
    """测试 Qdrant 服务是否可以连接"""
    max_retries = 3  # 增加重试次数
    for attempt in range(max_retries):
        try:
            # 尝试获取集合列表以测试连接
            collections = qdrant_client.get_collections()
            logger.info(f"成功连接到 Qdrant 服务: {collections}")
            assert collections is not None, "无法获取集合列表"
            return
        except Exception as e:
            logger.error(f"连接尝试 {attempt+1}/{max_retries} 失败: {type(e).__name__} - {str(e)}，错误详情: {e}")
            if attempt == max_retries - 1:
                pytest.fail(f"连接 Qdrant 服务失败: {e}")
            time.sleep(2)  # 等待2秒后重试

def test_qdrant_collection_creation(qdrant_client):
    """测试 Qdrant 是否可以创建集合"""
    collection_name = "test_collection"
    max_retries = 3  # 增加重试次数
    for attempt in range(max_retries):
        try:
            # 删除可能已存在的集合
            try:
                qdrant_client.delete_collection(collection_name)
            except Exception:
                pass
            
            # 创建新集合
            from qdrant_client.http.models import VectorParams, Distance
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=128, distance=Distance.COSINE)
            )
            logger.info(f"成功创建集合: {collection_name}")
            
            # 检查集合是否存在
            collections = qdrant_client.get_collections()
            assert collection_name in [col.name for col in collections.collections], f"集合 {collection_name} 未创建成功"
            return
        except Exception as e:
            logger.error(f"集合创建尝试 {attempt+1}/{max_retries} 失败: {type(e).__name__} - {str(e)}，错误详情: {e}")
            if attempt == max_retries - 1:
                pytest.fail(f"创建 Qdrant 集合失败: {e}")
            time.sleep(2)  # 等待2秒后重试
        finally:
            # 清理测试数据
            try:
                qdrant_client.delete_collection(collection_name)
            except Exception:
                pass