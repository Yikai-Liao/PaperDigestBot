"""
Configuration management using Pydantic and TOML
Provides type-safe configuration management for the PaperDigestBot system.
"""

import os
import sys
import tomllib
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseModel):
    """PostgreSQL database configuration"""

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    database: str = Field(default="paper_digest", description="Database name")
    user: str = Field(default="postgres", description="Database user")
    password: str = Field(default="root", description="Database password")
    min_connections: int = Field(default=1, description="Minimum connection pool size")
    max_connections: int = Field(default=10, description="Maximum connection pool size")
    ssl_mode: str | None = Field(default=None, description="SSL mode for connection")

    @property
    def dsn(self) -> str:
        """Returns database connection string"""
        ssl_part = f"?sslmode={self.ssl_mode}" if self.ssl_mode else ""
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}{ssl_part}"


class TelegramConfig(BaseModel):
    """Telegram bot configuration"""

    token: str = Field(description="Telegram bot token")
    webhook_url: str | None = Field(default=None, description="Webhook URL for Telegram")
    max_workers: int = Field(default=4, description="Maximum number of worker threads")
    reaction_mapping: dict[str, list[str]] = Field(
        default={
            "like": ["👍", "♥️", "🔥", "💯"],
            "dislike": ["👎", "💔", "😕"],
            "neutral": ["🤔", "😐", "😶"],
        },
        description="Mapping of preference types to Telegram reaction emojis",
    )


class SchedulerConfig(BaseModel):
    """APScheduler configuration"""

    timezone: str = Field(default="UTC", description="Default timezone for scheduled jobs")
    max_workers: int = Field(default=10, description="Maximum number of worker processes")
    coalesce: bool = Field(default=True, description="Coalesce jobs")
    max_instances: int = Field(default=3, description="Maximum instances of the same job")


class SecurityConfig(BaseModel):
    """Security configuration for PAT encryption"""

    encryption_key: str = Field(default="", description="Encryption key for GitHub PAT")


class AppConfig(BaseModel):
    """Main application configuration"""

    debug: bool = Field(default=False, description="Debug mode")
    test_mode: bool = Field(default=False, description="Test mode")
    log_level: str = Field(default="INFO", description="Logging level")


class Config(BaseSettings):
    """Main configuration class that combines all sub-configurations"""

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    app: AppConfig = Field(default_factory=AppConfig)

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
        case_sensitive = False

    @classmethod
    def from_toml(cls, config_path: Path) -> "Config":
        """Load configuration from TOML file"""
        try:
            with open(config_path, "rb") as f:
                toml_data = tomllib.load(f)

            # Override with environment variables
            env_overrides = cls._get_env_overrides()
            if env_overrides:
                toml_data = cls._merge_configs(toml_data, env_overrides)

            return cls(**toml_data)
        except FileNotFoundError:
            logger.warning(f"Config file {config_path} not found, using environment variables only")
            return cls()
        except tomllib.TOMLDecodeError as e:
            logger.error(f"Error parsing TOML config: {e}")
            raise
        except ValidationError as e:
            logger.error(f"Configuration validation error: {e}")
            raise

    @staticmethod
    def _get_env_overrides() -> dict[str, Any]:
        """Get configuration overrides from environment variables"""
        overrides = {}

        # Database overrides
        if db_host := os.getenv("POSTGRES_HOST"):
            overrides.setdefault("database", {})["host"] = db_host
        if db_port := os.getenv("POSTGRES_PORT"):
            overrides.setdefault("database", {})["port"] = int(db_port)
        if db_name := os.getenv("POSTGRES_DB"):
            overrides.setdefault("database", {})["database"] = db_name
        if db_user := os.getenv("POSTGRES_USER"):
            overrides.setdefault("database", {})["user"] = db_user
        if db_password := os.getenv("POSTGRES_PASSWORD"):
            overrides.setdefault("database", {})["password"] = db_password
        if ssl_mode := os.getenv("POSTGRES_SSL_MODE"):
            overrides.setdefault("database", {})["ssl_mode"] = ssl_mode

        # Telegram overrides
        if tg_token := os.getenv("TELEGRAM_BOT_TOKEN"):
            overrides.setdefault("telegram", {})["token"] = tg_token

        # Security overrides
        if enc_key := os.getenv("ENCRYPTION_KEY"):
            overrides.setdefault("security", {})["encryption_key"] = enc_key

        # App overrides
        if debug := os.getenv("DEBUG"):
            overrides.setdefault("app", {})["debug"] = debug.lower() == "true"
        if test_mode := os.getenv("TEST_MODE"):
            overrides.setdefault("app", {})["test_mode"] = test_mode.lower() == "true"
        if log_level := os.getenv("LOG_LEVEL"):
            overrides.setdefault("app", {})["log_level"] = log_level

        return overrides

    @staticmethod
    def _merge_configs(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Merge two configuration dictionaries"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = Config._merge_configs(result[key], value)
            else:
                result[key] = value
        return result


# Global configuration instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance"""
    global _config
    if _config is None:
        config_path = Path(__file__).parent.parent / "config" / "config.toml"
        _config = Config.from_toml(config_path)

        # Configure loguru
        logger.remove()  # Remove default handler
        logger.add(
            sys.stderr,
            level=_config.app.log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        )

    return _config


def reload_config() -> Config:
    """Reload configuration from file"""
    global _config
    _config = None
    return get_config()
