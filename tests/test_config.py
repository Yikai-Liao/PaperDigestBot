"""
Tests for the configuration management system
"""

import os
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import Config, DatabaseConfig, TelegramConfig


class TestDatabaseConfig:
    """Test database configuration"""

    def test_default_values(self) -> None:
        """Test default configuration values"""
        config = DatabaseConfig()
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "paper_digest"
        assert config.user == "postgres"
        assert config.password == "root"

    def test_dsn_generation(self) -> None:
        """Test DSN string generation"""
        config = DatabaseConfig(
            host="testhost", port=5433, database="testdb", user="testuser", password="testpass"
        )
        expected_dsn = "postgresql+psycopg2://testuser:testpass@testhost:5433/testdb"
        assert config.dsn == expected_dsn

    def test_dsn_with_ssl(self) -> None:
        """Test DSN string generation with SSL"""
        config = DatabaseConfig(ssl_mode="require")
        assert "?sslmode=require" in config.dsn


class TestTelegramConfig:
    """Test Telegram configuration"""

    def test_telegram_config_validation(self) -> None:
        """Test Telegram configuration validation"""
        config = TelegramConfig(token="test_token")
        assert config.token == "test_token"
        assert config.max_workers == 4

    def test_telegram_config_required_token(self) -> None:
        """Test that token is required"""
        with pytest.raises(ValidationError):
            TelegramConfig()


class TestConfig:
    """Test main configuration class"""

    def test_config_from_env(self) -> None:
        """Test configuration loading from environment variables"""
        # Store original values if they exist
        original_values = {}
        env_keys = [
            "DATABASE__HOST",
            "DATABASE__PORT",
            "TELEGRAM__TOKEN",
            "SECURITY__ENCRYPTION_KEY",
        ]
        for key in env_keys:
            original_values[key] = os.environ.get(key)

        try:
            # Set environment variables with proper nested naming
            os.environ.update(
                {
                    "DATABASE__HOST": "env_host",
                    "DATABASE__PORT": "5434",
                    "TELEGRAM__TOKEN": "env_token",
                    "SECURITY__ENCRYPTION_KEY": "env_key_32_chars_long_test_key",
                }
            )

            config = Config()
            assert config.database.host == "env_host"
            assert config.database.port == 5434
            assert config.telegram.token == "env_token"
            assert config.security.encryption_key == "env_key_32_chars_long_test_key"

        finally:
            # Restore original values
            for key in env_keys:
                if original_values[key] is not None:
                    os.environ[key] = original_values[key]
                else:
                    os.environ.pop(key, None)

    def test_config_from_toml(self) -> None:
        """Test configuration loading from TOML file"""
        toml_content = """
[database]
host = "toml_host"
port = 5435
database = "toml_db"

[telegram]
token = "toml_token"

[security]
encryption_key = "toml_key_32_chars_long_test_key"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            toml_path = Path(f.name)

        try:
            config = Config.from_toml(toml_path)
            assert config.database.host == "toml_host"
            assert config.database.port == 5435
            assert config.database.database == "toml_db"
            assert config.telegram.token == "toml_token"
            assert config.security.encryption_key == "toml_key_32_chars_long_test_key"
        finally:
            toml_path.unlink()

    def test_env_overrides_toml(self) -> None:
        """Test that environment variables override TOML values"""
        toml_content = """
[database]
host = "toml_host"

[telegram]
token = "toml_token"

[security]
encryption_key = "toml_key_32_chars_long_test_key"
"""

        # Store original value if it exists
        original_postgres_host = os.environ.get("POSTGRES_HOST")

        try:
            # Set environment variable
            os.environ["POSTGRES_HOST"] = "env_override_host"

            with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
                f.write(toml_content)
                toml_path = Path(f.name)

            try:
                config = Config.from_toml(toml_path)
                assert config.database.host == "env_override_host"  # Env should override TOML
                assert config.telegram.token == "toml_token"  # TOML value should remain
            finally:
                toml_path.unlink()
        finally:
            # Restore original value
            if original_postgres_host is not None:
                os.environ["POSTGRES_HOST"] = original_postgres_host
            else:
                os.environ.pop("POSTGRES_HOST", None)

    def test_missing_config_file(self) -> None:
        """Test handling of missing configuration file"""
        # Store original values if they exist
        original_token = os.environ.get("TELEGRAM__TOKEN")
        original_key = os.environ.get("SECURITY__ENCRYPTION_KEY")

        try:
            # Set required environment variables
            os.environ.update(
                {
                    "TELEGRAM__TOKEN": "test_token",
                    "SECURITY__ENCRYPTION_KEY": "test_key_32_chars_long_test_key",
                }
            )

            non_existent_path = Path("/non/existent/config.toml")
            config = Config.from_toml(non_existent_path)
            # Should fallback to environment variables
            assert config.telegram.token == "test_token"
        finally:
            # Restore original values
            if original_token is not None:
                os.environ["TELEGRAM__TOKEN"] = original_token
            else:
                os.environ.pop("TELEGRAM__TOKEN", None)
            if original_key is not None:
                os.environ["SECURITY__ENCRYPTION_KEY"] = original_key
            else:
                os.environ.pop("SECURITY__ENCRYPTION_KEY", None)
