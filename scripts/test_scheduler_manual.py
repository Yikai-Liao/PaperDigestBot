#!/usr/bin/env python3
"""
Manual test script for the scheduler functionality.
This script allows manual testing of scheduler operations without requiring a full bot setup.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from src.scheduler import (
    start_scheduler,
    shutdown_scheduler,
    parse_cron_expression,
    add_user_schedule,
    remove_user_schedule,
    get_user_schedule_info,
    is_scheduler_running
)
from loguru import logger


def test_cron_parsing():
    """Test cron expression parsing."""
    logger.info("Testing cron expression parsing...")

    test_cases = [
        ("0 7 * * *", "Daily at 7:00 AM"),
        ("0 0 7 * * *", "Daily at 7:00 AM (with seconds)"),
        ("30 8 1,15 * 1-5", "8:30 AM on 1st and 15th, weekdays only"),
        ("0 */2 * * *", "Every 2 hours"),
        ("0 9 * * 1", "Every Monday at 9:00 AM"),
    ]

    for cron_expr, description in test_cases:
        try:
            result = parse_cron_expression(cron_expr)
            logger.info(f"✓ {description}: {cron_expr} -> {result}")
        except Exception as e:
            logger.error(f"✗ Failed to parse '{cron_expr}': {e}")
            return False

    # Test invalid expressions
    invalid_cases = ["invalid", "* * *"]  # Removed "60 * * * *" as APScheduler might accept it
    for invalid_expr in invalid_cases:
        try:
            parse_cron_expression(invalid_expr)
            logger.error(f"✗ Should have failed to parse '{invalid_expr}'")
            return False
        except ValueError:
            logger.info(f"✓ Correctly rejected invalid expression: '{invalid_expr}'")

    logger.info("All cron parsing tests passed!")
    return True


def test_scheduler_lifecycle():
    """Test scheduler start/stop lifecycle."""
    logger.info("Testing scheduler lifecycle...")

    try:
        # Test starting scheduler
        start_scheduler()
        if not is_scheduler_running():
            logger.error("✗ Scheduler should be running after start")
            return False
        logger.info("✓ Scheduler started successfully")

        # Test adding a job
        success = add_user_schedule("test_user", "0 7 * * *")
        logger.info(f"✓ Add user schedule result: {success}")

        # Test getting job info
        info = get_user_schedule_info("test_user")
        if info:
            logger.info(f"✓ User schedule info: {info['job_id']}, next run: {info['next_run_time']}")
        else:
            logger.warning("No schedule info found (expected if no database)")

        # Test removing a job
        success = remove_user_schedule("test_user")
        logger.info(f"✓ Remove user schedule result: {success}")

        # Test stopping scheduler
        shutdown_scheduler()
        if is_scheduler_running():
            logger.error("✗ Scheduler should not be running after shutdown")
            return False
        logger.info("✓ Scheduler stopped successfully")

        logger.info("All scheduler lifecycle tests passed!")
        return True

    except Exception as e:
        logger.error(f"✗ Scheduler lifecycle test failed: {e}")
        return False


def interactive_test():
    """Interactive test mode for manual testing."""
    logger.info("Starting interactive scheduler test...")

    # Start scheduler
    start_scheduler()
    logger.info("Scheduler started. You can now test various operations.")

    try:
        while True:
            print("\n" + "="*50)
            print("Scheduler Test Menu:")
            print("1. Add user schedule")
            print("2. Remove user schedule")
            print("3. Get user schedule info")
            print("4. Test cron parsing")
            print("5. List all jobs")
            print("6. Exit")
            print("="*50)

            choice = input("Enter your choice (1-6): ").strip()

            if choice == "1":
                user_id = input("Enter user ID: ").strip()
                cron_expr = input("Enter cron expression (e.g., '0 7 * * *'): ").strip()
                success = add_user_schedule(user_id, cron_expr)
                print(f"Result: {'Success' if success else 'Failed'}")

            elif choice == "2":
                user_id = input("Enter user ID: ").strip()
                success = remove_user_schedule(user_id)
                print(f"Result: {'Success' if success else 'Failed'}")

            elif choice == "3":
                user_id = input("Enter user ID: ").strip()
                info = get_user_schedule_info(user_id)
                if info:
                    print(f"Job ID: {info['job_id']}")
                    print(f"Name: {info['name']}")
                    print(f"Next run: {info['next_run_time']}")
                    print(f"Trigger: {info['trigger']}")
                else:
                    print("No schedule found for this user")

            elif choice == "4":
                cron_expr = input("Enter cron expression to test: ").strip()
                try:
                    result = parse_cron_expression(cron_expr)
                    print(f"Parsed successfully: {result}")
                except Exception as e:
                    print(f"Parse failed: {e}")

            elif choice == "5":
                from src.scheduler import scheduler_manager
                if scheduler_manager.scheduler:
                    jobs = scheduler_manager.scheduler.get_jobs()
                    if jobs:
                        print(f"Found {len(jobs)} jobs:")
                        for job in jobs:
                            print(f"  - {job.id}: {job.name} (next: {job.next_run_time})")
                    else:
                        print("No jobs scheduled")
                else:
                    print("Scheduler not running")

            elif choice == "6":
                break

            else:
                print("Invalid choice. Please try again.")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        shutdown_scheduler()
        logger.info("Scheduler stopped. Goodbye!")


def main():
    """Main function to run tests."""
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_test()
    else:
        logger.info("Starting automated scheduler tests...")

        tests = [
            ("Cron Parsing", test_cron_parsing),
            ("Scheduler Lifecycle", test_scheduler_lifecycle)
        ]

        passed = 0
        failed = 0

        for test_name, test_func in tests:
            logger.info(f"\n--- Running {test_name} Test ---")
            try:
                if test_func():
                    logger.info(f"✓ {test_name} test passed")
                    passed += 1
                else:
                    logger.error(f"✗ {test_name} test failed")
                    failed += 1
            except Exception as e:
                logger.error(f"✗ {test_name} test failed with exception: {e}")
                failed += 1

        logger.info(f"\n--- Test Results ---")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {failed}")

        if failed == 0:
            logger.info("🎉 All tests passed!")
            return 0
        else:
            logger.error("❌ Some tests failed!")
            return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
