# scheduler.py - Scheduling system for PaperDigestBot

"""
APScheduler-based scheduling system for automated paper recommendations.
Uses PostgreSQL as job store for persistence and integrates with the Telegram bot.
"""

import asyncio
from typing import Optional, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from loguru import logger
import pytz
from telegram.ext import Application

from src.models import UserSetting, MessageRecord
from src.dispatcher import request_recommendations
from src.render import render_summary_tg
from src.db_config import default_config


class PaperDigestScheduler:
    """
    APScheduler-based scheduling system for automated paper recommendations.
    Manages cron-based scheduling for users and integrates with the Telegram bot.

    This class encapsulates all scheduling functionality and maintains a reference
    to the Telegram bot application for sending scheduled messages.
    """

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.bot_application: Optional[Application] = None

    def initialize(self, bot_application=None):
        """Initialize the APScheduler with PostgreSQL job store."""
        if self.scheduler is not None:
            logger.warning("Scheduler already initialized")
            return

        self.bot_application = bot_application

        # Configure job store using existing PostgreSQL connection
        jobstores = {
            'default': SQLAlchemyJobStore(url=default_config.dsn)
        }

        # Configure executors
        executors = {
            'default': AsyncIOExecutor()
        }

        # Job defaults
        job_defaults = {
            'coalesce': True,  # Coalesce missed executions
            'max_instances': 1,  # Only one instance per user
            'misfire_grace_time': 300  # 5 minutes grace time
        }

        # Create scheduler
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=pytz.UTC
        )

        logger.info("Scheduler initialized with PostgreSQL job store")

    def start(self):
        """Start the scheduler."""
        if self.scheduler is None:
            raise RuntimeError("Scheduler not initialized. Call initialize() first.")

        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")

            # Load existing user schedules
            self.load_all_user_schedules()
        else:
            logger.warning("Scheduler already running")

    def shutdown(self, wait: bool = True):
        """Shutdown the scheduler."""
        if self.scheduler is not None and self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info("Scheduler shutdown completed")
        else:
            logger.warning("Scheduler not running or not initialized")

    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self.scheduler is not None and self.scheduler.running

    def _parse_cron_to_kwargs(self, cron_expr: str) -> dict:
        """Parse cron expression to kwargs for APScheduler."""
        if not cron_expr or not cron_expr.strip():
            raise ValueError("Cron expression cannot be empty")

        parts = cron_expr.strip().split()

        if len(parts) == 5:
            # 5-field format: minute hour day month day_of_week
            minute, hour, day, month, day_of_week = parts
            return {
                'minute': minute,
                'hour': hour,
                'day': day,
                'month': month,
                'day_of_week': day_of_week,
                'timezone': pytz.UTC
            }
        elif len(parts) == 6:
            # 6-field format: second minute hour day month day_of_week
            second, minute, hour, day, month, day_of_week = parts
            return {
                'second': second,
                'minute': minute,
                'hour': hour,
                'day': day,
                'month': month,
                'day_of_week': day_of_week,
                'timezone': pytz.UTC
            }
        else:
            raise ValueError(f"Invalid cron expression format. Expected 5 or 6 fields, got {len(parts)}")



    def add_user_schedule(self, user_id: str, cron_expression: str) -> bool:
        """
        Add or update a user's scheduled recommendation job.

        Args:
            user_id: The user ID
            cron_expression: Cron expression for scheduling

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self.scheduler is None:
                logger.error("Scheduler not initialized")
                return False

            # Create job ID
            job_id = f"user_recommendation_{user_id}"

            # Use APScheduler's add_job with cron trigger directly
            # Use module-level function to avoid serialization issues
            self.scheduler.add_job(
                execute_scheduled_recommendation,
                'cron',
                args=[user_id],
                id=job_id,
                name=f"Recommendation for user {user_id}",
                replace_existing=True,
                **self._parse_cron_to_kwargs(cron_expression)
            )

            logger.info(f"Added scheduled job for user {user_id} with cron: {cron_expression}")
            return True

        except Exception as e:
            logger.error(f"Failed to add schedule for user {user_id}: {e}")
            return False

    def remove_user_schedule(self, user_id: str) -> bool:
        """
        Remove a user's scheduled recommendation job.

        Args:
            user_id: The user ID

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self.scheduler is None:
                logger.error("Scheduler not initialized")
                return False

            job_id = f"user_recommendation_{user_id}"

            # Check if job exists and remove it
            try:
                self.scheduler.remove_job(job_id)
                logger.info(f"Removed scheduled job for user {user_id}")
                return True
            except Exception:
                logger.info(f"No scheduled job found for user {user_id}")
                return True  # Not an error if job doesn't exist

        except Exception as e:
            logger.error(f"Failed to remove schedule for user {user_id}: {e}")
            return False

    def update_user_schedule(self, user_id: str, cron_expression: Optional[str]) -> bool:
        """
        Update a user's scheduled recommendation job.

        Args:
            user_id: The user ID
            cron_expression: New cron expression, or None to remove schedule

        Returns:
            bool: True if successful, False otherwise
        """
        if cron_expression is None or cron_expression.lower() == '关闭':
            return self.remove_user_schedule(user_id)
        else:
            return self.add_user_schedule(user_id, cron_expression)

    def get_user_schedule_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a user's scheduled job.

        Args:
            user_id: The user ID

        Returns:
            Dict with job information or None if no job exists
        """
        try:
            if self.scheduler is None:
                return None

            job_id = f"user_recommendation_{user_id}"
            job = self.scheduler.get_job(job_id)

            if job:
                return {
                    'job_id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time,
                    'trigger': str(job.trigger)
                }
            else:
                return None

        except Exception as e:
            logger.error(f"Failed to get schedule info for user {user_id}: {e}")
            return None

    def load_all_user_schedules(self):
        """
        Load all user schedules from database and add them to the scheduler.
        This should be called when the scheduler starts.
        """
        try:
            logger.info("Loading all user schedules from database")

            # Get all users with cron settings
            users_with_cron = UserSetting.get_all()
            active_schedules = 0

            for user_setting in users_with_cron:
                if user_setting.cron and user_setting.cron.strip():
                    if self.add_user_schedule(user_setting.id, user_setting.cron):
                        active_schedules += 1

            logger.info(f"Loaded {active_schedules} user schedules")

        except Exception as e:
            logger.error(f"Failed to load user schedules: {e}")

    def sync_user_schedule_from_settings(self, user_id: str) -> bool:
        """
        Synchronize a user's schedule based on their current database settings.

        Args:
            user_id: The user ID

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            user_setting = UserSetting.get_by_id(user_id)
            if not user_setting:
                logger.warning(f"User {user_id} not found, removing any existing schedule")
                return self.remove_user_schedule(user_id)

            return self.update_user_schedule(user_id, user_setting.cron)

        except Exception as e:
            logger.error(f"Failed to sync schedule for user {user_id}: {e}")
            return False


# Module-level function to avoid serialization issues with scheduler instances
async def execute_scheduled_recommendation(user_id: str):
    """
    Execute a scheduled recommendation for a user.
    This function will be called by APScheduler.

    Args:
        user_id: The user ID to generate recommendations for
    """
    try:
        logger.info(f"Executing scheduled recommendation for user {user_id}")

        # Get the global scheduler instance to access bot application
        scheduler = get_scheduler()

        # Check if bot application is available
        if scheduler.bot_application is None:
            logger.error("Bot application not available for scheduled recommendation")
            return

        # Get user settings to verify they still exist and are valid
        user_setting = UserSetting.get_by_id(user_id)
        if not user_setting:
            logger.warning(f"User {user_id} not found, removing schedule")
            scheduler.remove_user_schedule(user_id)
            return

        # Check if user still has cron setting
        if not user_setting.cron:
            logger.info(f"User {user_id} no longer has cron setting, removing scheduled job")
            scheduler.remove_user_schedule(user_id)
            return

        # Verify user has required settings
        if not user_setting.pat or not user_setting.github_id or not user_setting.repo_name:
            logger.warning(f"User {user_id} missing required settings for recommendations")
            # Send error message to user
            try:
                await scheduler.bot_application.bot.send_message(
                    chat_id=int(user_id),
                    text="⚠️ 定时推荐失败：您的设置不完整。请使用 /setting 命令检查并完善您的配置。"
                )
            except Exception as e:
                logger.error(f"Failed to send error message to user {user_id}: {e}")
            return

        # Request recommendations
        recommendations = await request_recommendations(user_id)
        if recommendations is None or len(recommendations) == 0:
            logger.info(f"No recommendations available for user {user_id}")
            # Optionally send a message to user about no recommendations
            try:
                await scheduler.bot_application.bot.send_message(
                    chat_id=int(user_id),
                    text="📚 定时推荐：目前没有新的论文推荐。"
                )
            except Exception as e:
                logger.error(f"Failed to send no-recommendations message to user {user_id}: {e}")
            return

        # Format recommendations for Telegram
        try:
            # Use thread pool for CPU-intensive rendering
            loop = asyncio.get_running_loop()
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor() as executor:
                formatted = await loop.run_in_executor(executor, render_summary_tg, recommendations)
        except Exception as e:
            logger.error(f"Failed to format recommendations for user {user_id}: {e}")
            return

        # Send recommendations to user
        try:
            # Send header message
            await scheduler.bot_application.bot.send_message(
                chat_id=int(user_id),
                text="📚 定时推荐：为您推荐的论文摘要如下："
            )

            # Send each recommendation and record messages
            send_results = []
            for rec_text in formatted.values():
                try:
                    # Try sending with Markdown first
                    result = await scheduler.bot_application.bot.send_message(
                        chat_id=int(user_id),
                        text=rec_text,
                        parse_mode='Markdown'
                    )
                    send_results.append(result)
                except Exception as markdown_error:
                    logger.warning(f"Failed to send message with Markdown, trying plain text: {markdown_error}")
                    try:
                        # Fallback to plain text without parse_mode
                        result = await scheduler.bot_application.bot.send_message(
                            chat_id=int(user_id),
                            text=rec_text
                        )
                        send_results.append(result)
                    except Exception as plain_error:
                        logger.error(f"Failed to send message even with plain text: {plain_error}")
                        send_results.append(plain_error)

            # Record messages to database (similar to process_recommendations_background)
            for result, arxiv_id in zip(send_results, recommendations['id']):
                try:
                    # Handle exceptions in send_results
                    if isinstance(result, Exception):
                        logger.error(f"发送定时推荐消息时出错: {result}")
                        continue

                    # Extract message_id from the Message object
                    message_id = None
                    if hasattr(result, 'message_id'):
                        message_id = result.message_id
                        logger.debug(f"成功提取定时推荐消息 message_id: {message_id}")
                    else:
                        logger.error(f"定时推荐消息对象没有message_id属性. 可用属性: {dir(result)}")
                        continue

                    if message_id is None:
                        logger.error(f"定时推荐消息 message_id为None，跳过记录")
                        continue

                    # Create message record
                    record = MessageRecord.create(
                        group_id=None,  # 定时推荐都是私聊
                        user_id=user_id,
                        message_id=message_id,
                        arxiv_id=arxiv_id,
                        repo_name=user_setting.repo_name,
                    )
                    logger.info(f"定时推荐消息记录创建成功 - ID: {record.id}, ArXiv: {arxiv_id}")
                except Exception as e:
                    logger.error(f"记录定时推荐消息时出错: {e}")
                    import traceback
                    logger.error(f"详细错误信息: {traceback.format_exc()}")

            logger.info(f"Successfully sent {len(formatted)} scheduled recommendations to user {user_id}")

        except Exception as e:
            logger.error(f"Failed to send scheduled recommendations to user {user_id}: {e}")

    except Exception as e:
        logger.error(f"Error in scheduled recommendation for user {user_id}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


# Global scheduler instance for the application
_scheduler_instance: Optional[PaperDigestScheduler] = None


def get_scheduler() -> PaperDigestScheduler:
    """Get the global scheduler instance, creating it if necessary."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = PaperDigestScheduler()
    return _scheduler_instance


# Public API functions for integration with the bot
def start_scheduler(bot_app: Optional[Application] = None):
    """
    Initialize and start the scheduler.

    Args:
        bot_app: The Telegram bot application instance
    """
    try:
        scheduler = get_scheduler()
        scheduler.initialize(bot_app)
        scheduler.start()

        logger.info("Scheduler started successfully")

    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        raise


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    global _scheduler_instance

    try:
        if _scheduler_instance is not None:
            _scheduler_instance.shutdown()
            _scheduler_instance = None
            logger.info("Scheduler shutdown completed")
    except Exception as e:
        logger.error(f"Error during scheduler shutdown: {e}")


def is_scheduler_running() -> bool:
    """Check if the scheduler is running."""
    global _scheduler_instance
    return _scheduler_instance is not None and _scheduler_instance.is_running()


def sync_user_schedule_from_settings(user_id: str) -> bool:
    """
    Synchronize a user's schedule based on their current database settings.

    Args:
        user_id: The user ID

    Returns:
        bool: True if successful, False otherwise
    """
    scheduler = get_scheduler()
    return scheduler.sync_user_schedule_from_settings(user_id)


