"""
数据库连接管理
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator
from loguru import logger
from .db_config import default_config

class Database:
    """数据库连接管理类"""
    
    _instance = None
    _engine = None
    _session_factory = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance
    
    def initialize(self):
        """初始化数据库连接"""
        if self._engine is None:
            try:
                # 创建 PostgreSQL 数据库引擎
                self._engine = create_engine(
                    default_config.dsn,
                    pool_size=default_config.max_connections,
                    max_overflow=0
                )
                
                # 创建会话工厂
                self._session_factory = sessionmaker(
                    bind=self._engine,
                    expire_on_commit=False
                )
                
                logger.info("数据库连接初始化成功")
                
            except Exception as e:
                logger.error(f"数据库连接初始化失败: {e}")
                raise
    
    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """获取数据库会话的上下文管理器"""
        if not self._session_factory:
            self.initialize()
            
        session = self._session_factory()
        try:
            yield session
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    @property
    def engine(self):
        """获取数据库引擎"""
        if not self._engine:
            self.initialize()
        return self._engine
    
    def close(self) -> None:
        """关闭数据库连接"""
        if self._engine:
            self._engine.dispose()
            logger.info("数据库连接已关闭")

# 创建默认数据库实例
db = Database() 