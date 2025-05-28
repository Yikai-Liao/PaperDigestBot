#!/usr/bin/env python3
"""
Development script for PaperDigestBot

This script provides various development commands to replace Makefile functionality.
Run with --help to see available commands.
"""

import argparse
import subprocess
import sys
from pathlib import Path


class DevScript:
    """Development script for managing project tasks."""

    def __init__(self):
        self.project_root = Path(__file__).parent

    def run_command(self, command: str, description: str = "") -> int:
        """Run a shell command and return its exit code."""
        if description:
            print(f">>> {description}")
        print(f"$ {command}")

        try:
            result = subprocess.run(command, shell=True, cwd=self.project_root)
            return result.returncode
        except KeyboardInterrupt:
            print("\nCommand interrupted by user")
            return 130

    def setup_dev(self) -> int:
        """Setup development environment."""
        print("Setting up development environment...")

        commands = [
            ("uv sync --no-progress", "Installing dependencies"),
            ("uv run pre-commit install", "Installing pre-commit hooks"),
        ]

        for command, desc in commands:
            if self.run_command(command, desc) != 0:
                return 1

        print("Development environment setup complete!")
        return 0

    def test(self) -> int:
        """Run all tests with Docker containers."""
        print("Running all tests...")

        # Start test containers
        if (
            self.run_command(
                "docker compose -f docker-compose.test.yml up -d", "Starting test containers"
            )
            != 0
        ):
            return 1

        try:
            # Run tests
            result = self.run_command("uv run pytest --no-header -v", "Running tests")
        finally:
            # Clean up containers
            self.run_command(
                "docker compose -f docker-compose.test.yml down", "Cleaning up test containers"
            )

        return result

    def test_unit(self) -> int:
        """Run unit tests only."""
        return self.run_command("uv run pytest -m unit --no-header -v", "Running unit tests")

    def test_integration(self) -> int:
        """Run integration tests."""
        return self.run_command(
            "uv run pytest -m integration --no-header -v", "Running integration tests"
        )

    def test_slow(self) -> int:
        """Run slow tests."""
        return self.run_command("uv run pytest -m slow --no-header -v", "Running slow tests")

    def lint(self) -> int:
        """Run linting checks."""
        print("Running linting checks...")

        commands = [
            ("uv run ruff check .", "Running ruff"),
            ("uv run black --check .", "Running black"),
            ("uv run isort --check-only .", "Running isort"),
        ]

        exit_code = 0
        for command, desc in commands:
            if self.run_command(command, desc) != 0:
                exit_code = 1

        return exit_code

    def format(self) -> int:
        """Auto-format code."""
        print("Formatting code...")

        commands = [
            ("uv run black .", "Running black"),
            ("uv run isort .", "Running isort"),
            ("uv run ruff check --fix .", "Running ruff with auto-fix"),
        ]

        for command, desc in commands:
            if self.run_command(command, desc) != 0:
                return 1

        return 0

    def type_check(self) -> int:
        """Run mypy type checking."""
        return self.run_command("uv run mypy src tests", "Running mypy type checking")

    def docker_test(self) -> int:
        """Start test database containers."""
        return self.run_command(
            "docker compose -f docker-compose.test.yml up -d", "Starting test containers"
        )

    def docker_clean(self) -> int:
        """Clean up test containers."""
        return self.run_command(
            "docker compose -f docker-compose.test.yml down", "Cleaning up test containers"
        )

    def run(self) -> int:
        """Run the bot."""
        return self.run_command("uv run python -m src.bot.tg", "Starting the bot")

    def db_init(self) -> int:
        """Initialize production database."""
        return self.run_command("uv run alembic upgrade head", "Initializing database")

    def db_clean(self) -> int:
        """Clean production database."""
        return self.run_command("uv run alembic downgrade base", "Cleaning database")

    def help(self) -> int:
        """Show available commands."""
        commands = {
            "setup-dev": "Setup development environment",
            "test": "Run all tests with Docker containers",
            "test-unit": "Run unit tests only",
            "test-integration": "Run integration tests",
            "test-slow": "Run slow tests",
            "lint": "Run linting checks (ruff, black, isort)",
            "format": "Auto-format code",
            "type-check": "Run mypy type checking",
            "docker-test": "Start test database containers",
            "docker-clean": "Clean up test containers",
            "run": "Run the bot",
            "db-init": "Initialize production database",
            "db-clean": "Clean production database",
            "help": "Show this help message",
        }

        print("Available commands:")
        print()
        for cmd, desc in commands.items():
            print(f"  {cmd:<20} {desc}")
        print()
        print("Usage: python dev.py <command>")
        print("       uv run python dev.py <command>")
        return 0


def main():
    """Main entry point."""
    dev = DevScript()

    parser = argparse.ArgumentParser(
        description="Development script for PaperDigestBot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="help",
        help="Command to run (default: help)",
    )

    args = parser.parse_args()

    # Get the command method
    command_method = getattr(dev, args.command.replace("-", "_"), None)
    if not command_method:
        print(f"Unknown command: {args.command}")
        print("Run 'python dev.py help' to see available commands")
        return 1

    # Run the command
    try:
        return command_method()
    except Exception as e:
        print(f"Error running command '{args.command}': {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
