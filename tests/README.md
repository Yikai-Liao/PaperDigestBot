# Tests

This directory contains all test files for the PaperDigestBot project.

## Structure

- `test_scheduler.py` - Tests for the APScheduler-based scheduling system
- `__init__.py` - Makes this directory a Python package

## Running Tests

### Using pytest (recommended)

```bash
# Run all tests
uv run pytest tests/

# Run specific test file
uv run pytest tests/test_scheduler.py

# Run with verbose output
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=src
```

### Using unittest

```bash
# Run specific test file
uv run python -m pytest tests/test_scheduler.py
```

## Test Categories

### Scheduler Tests (`test_scheduler.py`)

- **Cron Parsing Tests**: Test parsing of various cron expression formats
- **Scheduler Lifecycle Tests**: Test initialization, start, and shutdown
- **Job Management Tests**: Test adding, removing, and updating scheduled jobs
- **Scheduled Execution Tests**: Test the actual execution of scheduled recommendations

## Writing New Tests

When adding new tests:

1. Create test files with the `test_` prefix
2. Use pytest conventions for test classes and methods
3. Include proper docstrings explaining what each test does
4. Use appropriate mocking for external dependencies
5. Follow the existing test structure and patterns

## Dependencies

Tests use the following testing libraries:
- `pytest` - Main testing framework
- `pytest-asyncio` - For testing async functions
- `unittest.mock` - For mocking dependencies
