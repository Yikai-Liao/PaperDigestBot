"""
数据库配置文件
包含 PostgreSQL 数据库连接参数
"""
from dataclasses import dataclass
from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables from .env file
# This ensures that when DBConfig is defined, it can access these variables
load_dotenv()

@dataclass
class DBConfig:
    """PostgreSQL 数据库配置"""
    host: str = os.getenv('POSTGRES_HOST', "localhost")
    port: int = int(os.getenv('POSTGRES_PORT', "5432"))
    database: str = os.getenv('POSTGRES_DB', "paper_digest")
    user: str = os.getenv('POSTGRES_USER', "postgres")
    password: str = os.getenv('POSTGRES_PASSWORD', "root")
    min_connections: int = int(os.getenv('DB_MIN_CONNECTIONS', "1"))
    max_connections: int = int(os.getenv('DB_MAX_CONNECTIONS', "10"))
    ssl_mode: Optional[str] = os.getenv('POSTGRES_SSL_MODE', None)

    @property
    def dsn(self) -> str:
        """返回数据库连接字符串"""
        ssl_part = f"?sslmode={self.ssl_mode}" if self.ssl_mode else ""
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}{ssl_part}"

# 默认配置实例
default_config = DBConfig()