import os
import sys
from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

# 获取项目根目录路径
REPO_DIR = Path(__file__).resolve().parent.parent
# 加载环境变量
load_dotenv(REPO_DIR / ".env")
# 将 src 目录添加到 Python 路径中
sys.path.append(str(REPO_DIR))

from src.models.base import BaseModel

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config


# 从环境变量构建数据库连接字符串
def get_database_url():
    """从环境变量获取数据库连接字符串"""
    host = os.getenv("DATABASE__HOST", "localhost")
    port = os.getenv("DATABASE__PORT", "5432")
    user = os.getenv("DATABASE__USER", "postgres")
    password = os.getenv("DATABASE__PASSWORD", "root")
    database = os.getenv("DATABASE__DATABASE", "paper_digest")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


# 设置数据库连接字符串
config.set_main_option("sqlalchemy.url", get_database_url())

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = BaseModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
