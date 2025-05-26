# PaperDigestBot

一个智能的论文推荐和摘要机器人，通过 Telegram 为用户提供个性化的 arXiv 论文推荐服务。

## 📖 项目概述

PaperDigestBot 是一个基于 Telegram 的智能论文推荐系统，它能够：

- 🤖 **自动化论文推荐**：通过 GitHub Actions 工作流自动获取和处理最新的 arXiv 论文
- 📅 **定时推送**：支持用户自定义 Cron 表达式，定时接收论文推荐
- 💾 **反应记录**：记录用户对论文的反应（点赞、点踩等），用于改进推荐算法
- ⚙️ **个性化配置**：支持用户配置 GitHub 仓库、访问令牌等个人设置
- 🗄️ **数据持久化**：使用 PostgreSQL 数据库存储用户设置、消息记录和反应数据

## ✨ 主要功能

### 已实现功能

- **论文推荐** (`/recommend`)：获取个性化的论文推荐和摘要
- **用户设置** (`/setting`)：配置 GitHub PAT、仓库名称、定时任务等
- **定时推送**：基于 APScheduler 的自动化定时推荐系统
- **反应记录**：记录和追踪用户对论文的反应表情
- **消息记录**：完整的消息历史和论文交互记录
- **多用户支持**：支持多个用户独立配置和使用

### 核心组件

- **Telegram Bot** (`src/bot/tg.py`)：处理用户交互和消息
- **调度器** (`src/scheduler.py`)：基于 APScheduler 的定时任务管理
- **分发器** (`src/dispatcher.py`)：任务分发和设置管理
- **GitHub Actions 集成** (`src/action.py`)：触发和管理 GitHub 工作流
- **数据模型** (`src/models/`)：用户设置、消息记录、反应记录等

## 🚀 安装指南

### 环境要求

- Python 3.12+
- PostgreSQL 数据库
- Podman 或 Docker（用于数据库容器）
- GitHub Personal Access Token
- Telegram Bot Token

### 使用 uv 安装

本项目推荐使用 `uv` 作为包管理器：

```bash
# 克隆项目
git clone https://github.com/Yikai-Liao/PaperDigestBot.git
cd PaperDigestBot

# 使用 uv 安装依赖
uv sync

# 或者如果你还没有安装 uv
pip install uv
uv sync
```

### 数据库初始化

使用 Podman 初始化 PostgreSQL 数据库，确保你的 `vchord-postgres` 容器正在运行，并且 `.env` 文件中正确配置了 `POSTGRES_USER` 和 `POSTGRES_DB`。

然后从项目根目录运行以下命令：

```bash
podman exec -i vchord-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/init.sql
```

此命令在运行的 `vchord-postgres` 容器内执行 `db/init.sql` 脚本，为应用程序设置必要的表和模式。

**故障排除：**

如果遇到 `UndefinedColumn` 错误（例如 `created_at`），这可能意味着数据库模式没有正确更新。解决方法：

1. 停止 Python 应用程序和 `vchord-postgres` Podman 容器
2. **重要：删除旧的数据库数据卷**。如果你映射了主机目录（例如 `./pg_data`），删除它：`rm -rf ./pg_data`。如果是命名的 Podman 卷，使用 `podman volume rm <volume_name>`。**警告：**这将删除所有现有的数据库数据
3. 重启 `vchord-postgres` 容器。这将创建一个新的空数据库
4. 重新运行上面的 `podman exec ... psql ... < db/init.sql` 命令以应用最新的模式
5. 重启 Python 应用程序
