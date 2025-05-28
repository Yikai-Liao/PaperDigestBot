"""
Database configuration compatibility module
Provides backward compatibility for the old DBConfig interface.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# Import the new configuration system
from src.config import get_config


class DBConfig:
    """Legacy database configuration wrapper for backward compatibility"""

    def __init__(self) -> None:
        self._config = get_config()

    @property
    def host(self) -> str:
        return self._config.database.host

    @property
    def port(self) -> int:
        return self._config.database.port

    @property
    def database(self) -> str:
        return self._config.database.database

    @property
    def user(self) -> str:
        return self._config.database.user

    @property
    def password(self) -> str:
        return self._config.database.password

    @property
    def min_connections(self) -> int:
        return self._config.database.min_connections

    @property
    def max_connections(self) -> int:
        return self._config.database.max_connections

    @property
    def ssl_mode(self) -> str | None:
        return self._config.database.ssl_mode

    @property
    def dsn(self) -> str:
        """返回数据库连接字符串"""
        return self._config.database.dsn


# 默认配置实例，保持向后兼容
default_config = DBConfig()
