# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Quick Start:**
- `python dev.py help` - Show all available commands
- `python dev.py setup-dev` - Setup development environment
- `python dev.py test` - Run all tests with Docker containers
- `python dev.py run` - Run the bot

**Testing:**
- `python dev.py test` - Run all tests (includes Docker setup)
- `python dev.py test-unit` - Run unit tests only
- `python dev.py test-integration` - Run integration tests
- `python dev.py test-slow` - Run slow tests
- `uv run pytest tests/test_render.py` - Run specific test file
- `uv run pytest -v -m unit` - Run unit tests with verbose output

**Coverage Testing:**
- `uv run pytest --cov=src --cov-report=html --cov-report=xml --cov-report=term-missing tests/` - Run tests with coverage report
- Coverage reports are generated in:
  - `htmlcov/index.html` - Interactive HTML coverage report
  - `coverage.xml` - XML coverage report for CI/CD integration
  - Terminal output with missing lines highlighted

**Code Quality:**
- `python dev.py lint` - Run linting checks (ruff, black, isort)
- `python dev.py format` - Auto-format code
- `python dev.py type-check` - Run mypy type checking

**Environment:**
- `uv sync` - Install dependencies using uv package manager
- `uv sync --no-dev` - Install production dependencies only
- `python dev.py setup-dev` - Setup development environment
- `uv run <command>` - Run commands in the virtual environment

**Database:**
- `python dev.py docker-test` - Start test database containers
- `python dev.py docker-clean` - Clean up test containers
- `uv run alembic upgrade head` - Initialize/update database schema
- `uv run alembic current` - Check current migration status
- `uv run alembic revision --autogenerate -m "description"` - Create new migration

## Architecture Overview

This is a Telegram bot system for arXiv paper recommendations with the following core components:

### Core Architecture
- **Telegram Bot** (`src/bot/tg.py`): Handles user interactions, commands, and message processing
  - `/start` - Welcome message and bot introduction
  - `/recommend` - Get paper recommendations (background processing)
  - `/setting` - Configure user preferences and GitHub integration
  - `/sync` - Manually sync preference data to GitHub (background processing)
- **Scheduler** (`src/scheduler.py`): APScheduler-based system for automated cron-scheduled recommendations using PostgreSQL job store
- **Dispatcher** (`src/dispatcher.py`): Task dispatching and user settings management  
- **Preference Manager** (`src/preference.py`): Handles user preference tracking and GitHub repository sync
- **GitHub Actions Integration** (`src/action.py`): Triggers external workflows for paper processing
- **Render** (`src/render.py`): Formats paper summaries for Telegram with MarkdownV2 support

### Data Models (`src/models/`)
- **UserSetting**: Stores user GitHub PAT, repository info, and cron schedules
- **MessageRecord**: Tracks sent messages for reaction handling
- **ReactionRecord**: Records user reactions to papers for feedback

### Preference Management System
- **Reaction Tracking**: Users react to recommended papers with emojis (👍♥️🔥 = like, 👎💔 = dislike, 🤔😐 = neutral)
- **Automatic Sync**: Daily sync at UTC 00:00 uploads preference data to user's GitHub repository
- **Manual Sync**: Users can trigger `/sync` command to immediately sync their preferences
- **CSV Format**: Preferences stored as CSV files in `preference/YYYY-MM.csv` format
- **Data Deduplication**: Uses DuckDB for merging new reactions with existing preference data

### Key Integration Points
- Uses PostgreSQL for persistence (user settings, job store, message records)
- APScheduler integrates with Telegram bot application for scheduled message delivery
- GitHub workflow integration fetches and processes arXiv papers
- Settings format: `repo:USER/REPO;pat:YOUR_PAT;cron:0 0 7 * * *;timezone:Asia/Shanghai`

### Configuration
- Environment variables loaded from `.env` file
- Config in `config/config.toml` for Telegram token and PAT encryption
- Database connection configured in `src/db_config.py`

### Error Handling
- Graceful Markdown fallback to plain text for message sending
- Missing user settings validation in scheduled tasks
- Database transaction management through SQLAlchemy models