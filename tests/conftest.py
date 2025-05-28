"""
Pytest configuration and fixtures for PaperDigestBot tests
Provides database setup, test data, and common utilities for testing.
"""

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from src.config import Config, get_config
from src.db import Database
from src.models.base import BaseModel


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    """Start a PostgreSQL container for testing."""
    with PostgresContainer("postgres:15") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def test_database_url(postgres_container: PostgresContainer) -> str:
    """Get the database URL for testing."""
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session")
def test_config(postgres_container: PostgresContainer) -> Config:
    """Create a test configuration."""
    # Override environment variables for testing
    os.environ.update(
        {
            "POSTGRES_HOST": postgres_container.get_container_host_ip(),
            "POSTGRES_PORT": str(postgres_container.get_exposed_port(5432)),
            "POSTGRES_DB": postgres_container.dbname,
            "POSTGRES_USER": postgres_container.username,
            "POSTGRES_PASSWORD": postgres_container.password,
            "TELEGRAM_BOT_TOKEN": "test_token",
            "ENCRYPTION_KEY": "test_encryption_key_32_chars_long",
            "TEST_MODE": "true",
        }
    )

    # Create test config
    config = Config(
        database={
            "host": postgres_container.get_container_host_ip(),
            "port": postgres_container.get_exposed_port(5432),
            "database": postgres_container.dbname,
            "user": postgres_container.username,
            "password": postgres_container.password,
        },
        telegram={"token": "test_token"},
        security={"encryption_key": "test_encryption_key_32_chars_long"},
        app={"test_mode": True},
    )

    return config


@pytest.fixture(scope="session")
def setup_database(test_config: Config) -> Generator[None, None, None]:
    """Set up the test database with required tables."""
    engine = create_engine(test_config.database.dsn)

    # Create all tables using Alembic
    from alembic import command
    from alembic.config import Config as AlembicConfig

    # Run alembic migrations to create tables
    alembic_cfg = AlembicConfig("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", test_config.database.dsn)
    command.upgrade(alembic_cfg, "head")

    yield

    # Cleanup
    BaseModel.metadata.drop_all(engine)


@pytest_asyncio.fixture
async def db_session(test_config: Config, setup_database: None) -> AsyncGenerator[Database, None]:
    """Create a database session for testing."""
    # For testing, we'll patch the configuration directly
    import src.db_config

    original_config = src.db_config.default_config._config

    # Create a new DBConfig instance with test config
    test_db_config = src.db_config.DBConfig()
    test_db_config._config = test_config
    src.db_config.default_config = test_db_config

    db = Database()
    db.initialize()
    yield db

    # Restore original config
    src.db_config.default_config._config = original_config


@pytest.fixture
def sample_user_data() -> dict:
    """Sample user data for testing."""
    return {
        "id": "test_user_123",
        "github_id": "testuser",
        "repo_name": "test-repo",
        "pat": "test_pat_token",
        "cron": "0 9 * * *",
        "timezone": "Asia/Shanghai",
    }


@pytest.fixture
def sample_settings_text() -> str:
    """Sample settings text for parsing tests."""
    return "repo:testuser/test-repo;pat:test_pat_token;cron:0 9 * * *;timezone:Asia/Shanghai"


@pytest.fixture
def invalid_settings_text() -> str:
    """Invalid settings text for error testing."""
    return "repo:invalid_format;pat:;cron:invalid_cron"
