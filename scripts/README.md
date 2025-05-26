# Scripts

This directory contains utility and development scripts for the PaperDigestBot project.

## Available Scripts

### `test_scheduler_manual.py`

Manual testing script for the scheduler functionality. Provides both automated and interactive testing modes.

**Usage:**

```bash
# Run automated tests
uv run python scripts/test_scheduler_manual.py

# Run interactive test mode
uv run python scripts/test_scheduler_manual.py --interactive
```

**Features:**
- Automated testing of cron parsing and scheduler lifecycle
- Interactive mode for manual testing of scheduler operations
- Real-time job management and monitoring
- Cron expression validation testing

**Interactive Mode Commands:**
1. Add user schedule - Create a new scheduled job for a user
2. Remove user schedule - Remove an existing scheduled job
3. Get user schedule info - View details about a user's scheduled job
4. Test cron parsing - Validate cron expressions
5. List all jobs - Show all currently scheduled jobs
6. Exit - Stop the script and shutdown scheduler

## Adding New Scripts

When creating new utility scripts:

1. Place them in this `scripts/` directory
2. Use descriptive names that indicate the script's purpose
3. Include proper shebang line (`#!/usr/bin/env python3`)
4. Add comprehensive docstrings and help text
5. Handle command-line arguments appropriately
6. Include error handling and logging
7. Update this README with script descriptions

## Running Scripts

All scripts should be run using `uv run` to ensure proper dependency management:

```bash
uv run python scripts/script_name.py
```
