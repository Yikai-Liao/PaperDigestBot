"""
Test suite for the PaperDigestScheduler functionality.
Tests the object-oriented APScheduler integration with real-world scenarios.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from telegram.ext import Application

from src.scheduler import (
    PaperDigestScheduler,
    get_scheduler,
    start_scheduler,
    shutdown_scheduler,
    is_scheduler_running,
    sync_user_schedule_from_settings
)


class TestPaperDigestScheduler:
    """Test the PaperDigestScheduler class functionality."""

    def setup_method(self):
        """Setup for each test method."""
        self.scheduler = PaperDigestScheduler()

    def teardown_method(self):
        """Cleanup after each test method."""
        if self.scheduler.scheduler is not None:
            self.scheduler.shutdown()

    @patch('src.scheduler.default_config')
    def test_scheduler_initialization_with_mock_db(self, mock_config):
        """Test scheduler initialization with mocked database config."""
        mock_config.dsn = "sqlite:///:memory:"
        mock_bot = Mock(spec=Application)

        # Test initialization
        self.scheduler.initialize(mock_bot)

        assert self.scheduler.scheduler is not None
        assert self.scheduler.bot_application == mock_bot
        assert not self.scheduler.is_running()

    @patch('src.scheduler.default_config')
    def test_scheduler_initialization(self, mock_config):
        """Test scheduler initialization."""
        mock_config.dsn = "sqlite:///:memory:"
        mock_bot = Mock(spec=Application)

        # Test initialization
        self.scheduler.initialize(mock_bot)

        assert self.scheduler.scheduler is not None
        assert self.scheduler.bot_application == mock_bot
        assert not self.scheduler.is_running()

    @patch('src.scheduler.default_config')
    @patch('src.scheduler.UserSetting')
    @patch('src.scheduler.AsyncIOScheduler')
    def test_scheduler_start_stop(self, mock_scheduler_class, mock_user_setting, mock_config):
        """Test scheduler start and stop."""
        mock_config.dsn = "sqlite:///:memory:"
        mock_user_setting.get_all.return_value = []
        mock_bot = Mock(spec=Application)

        # Mock the scheduler instance
        mock_scheduler_instance = Mock()
        mock_scheduler_instance.running = False
        mock_scheduler_class.return_value = mock_scheduler_instance

        # Initialize
        self.scheduler.initialize(mock_bot)

        # Test start
        self.scheduler.start()
        mock_scheduler_instance.start.assert_called_once()

        # Mock running state for is_running check
        mock_scheduler_instance.running = True
        assert self.scheduler.is_running()

        # Test stop
        self.scheduler.shutdown()
        mock_scheduler_instance.shutdown.assert_called_once()

    def test_cron_parsing(self):
        """Test cron expression parsing."""
        test_cases = [
            ("0 7 * * *", 5),      # 5-field
            ("0 0 7 * * *", 6),    # 6-field
            ("*/15 9-17 * * 1-5", 5),  # Complex expression
        ]

        for cron_expr, expected_fields in test_cases:
            result = self.scheduler._parse_cron_to_kwargs(cron_expr)
            assert 'timezone' in result
            # Count non-timezone fields
            field_count = len([k for k in result.keys() if k != 'timezone'])
            assert field_count == expected_fields, f"Expected {expected_fields} fields for {cron_expr}"

    def test_invalid_cron_expressions(self):
        """Test that invalid cron expressions raise errors."""
        invalid_expressions = [
            "",                    # Empty
            "* * *",              # Too few fields
            "* * * * * * * *",    # Too many fields
        ]

        for expr in invalid_expressions:
            with pytest.raises(ValueError):
                self.scheduler._parse_cron_to_kwargs(expr)

    @patch('src.scheduler.default_config')
    @patch('src.scheduler.UserSetting')
    @patch('src.scheduler.AsyncIOScheduler')
    def test_add_user_schedule(self, mock_scheduler_class, mock_user_setting, mock_config):
        """Test adding a user schedule."""
        mock_config.dsn = "sqlite:///:memory:"
        mock_user_setting.get_all.return_value = []
        mock_bot = Mock(spec=Application)

        # Mock the scheduler instance
        mock_scheduler_instance = Mock()
        mock_scheduler_instance.running = True
        mock_scheduler_class.return_value = mock_scheduler_instance

        # Mock job info
        mock_job = Mock()
        mock_job.id = "user_recommendation_test_user_123"
        mock_job.name = "Recommendation for user test_user_123"
        mock_job.next_run_time = None
        mock_job.trigger = "cron"
        mock_scheduler_instance.get_job.return_value = mock_job

        self.scheduler.initialize(mock_bot)
        self.scheduler.start()

        user_id = "test_user_123"
        cron_expr = "0 7 * * *"

        result = self.scheduler.add_user_schedule(user_id, cron_expr)

        assert result is True
        mock_scheduler_instance.add_job.assert_called_once()

        # Check that job was added
        job_info = self.scheduler.get_user_schedule_info(user_id)
        assert job_info is not None
        assert job_info['job_id'] == f"user_recommendation_{user_id}"

    @patch('src.scheduler.default_config')
    @patch('src.scheduler.UserSetting')
    @patch('src.scheduler.AsyncIOScheduler')
    def test_remove_user_schedule(self, mock_scheduler_class, mock_user_setting, mock_config):
        """Test removing a user schedule."""
        mock_config.dsn = "sqlite:///:memory:"
        mock_user_setting.get_all.return_value = []
        mock_bot = Mock(spec=Application)

        # Mock the scheduler instance
        mock_scheduler_instance = Mock()
        mock_scheduler_instance.running = True
        mock_scheduler_class.return_value = mock_scheduler_instance

        # Mock job removal
        mock_scheduler_instance.get_job.side_effect = [Mock(), None]  # First call returns job, second returns None

        self.scheduler.initialize(mock_bot)
        self.scheduler.start()

        user_id = "test_user_123"
        cron_expr = "0 7 * * *"

        # Add schedule first (mocked)
        self.scheduler.add_user_schedule(user_id, cron_expr)

        # Remove schedule
        result = self.scheduler.remove_user_schedule(user_id)

        assert result is True
        mock_scheduler_instance.remove_job.assert_called_once()

    @patch('src.scheduler.default_config')
    @patch('src.scheduler.UserSetting')
    @patch('src.scheduler.AsyncIOScheduler')
    def test_update_user_schedule(self, mock_scheduler_class, mock_user_setting, mock_config):
        """Test updating a user schedule."""
        mock_config.dsn = "sqlite:///:memory:"
        mock_user_setting.get_all.return_value = []
        mock_bot = Mock(spec=Application)

        # Mock the scheduler instance
        mock_scheduler_instance = Mock()
        mock_scheduler_instance.running = True
        mock_scheduler_class.return_value = mock_scheduler_instance

        # Mock job info
        mock_job = Mock()
        mock_job.id = "user_recommendation_test_user_123"
        mock_scheduler_instance.get_job.return_value = mock_job

        self.scheduler.initialize(mock_bot)
        self.scheduler.start()

        user_id = "test_user_123"
        old_cron = "0 7 * * *"
        new_cron = "0 8 * * *"

        # Add initial schedule (mocked)
        self.scheduler.add_user_schedule(user_id, old_cron)

        # Update schedule
        result = self.scheduler.update_user_schedule(user_id, new_cron)

        assert result is True

        # Verify job still exists (it should be replaced)
        job_info = self.scheduler.get_user_schedule_info(user_id)
        assert job_info is not None

    @patch('src.scheduler.default_config')
    @patch('src.scheduler.UserSetting')
    @patch('src.scheduler.AsyncIOScheduler')
    def test_update_schedule_to_disable(self, mock_scheduler_class, mock_user_setting, mock_config):
        """Test updating schedule to '关闭' (should remove it)."""
        mock_config.dsn = "sqlite:///:memory:"
        mock_user_setting.get_all.return_value = []
        mock_bot = Mock(spec=Application)

        # Mock the scheduler instance
        mock_scheduler_instance = Mock()
        mock_scheduler_instance.running = True
        mock_scheduler_class.return_value = mock_scheduler_instance

        # Mock job removal
        mock_scheduler_instance.get_job.side_effect = [Mock(), None]  # First call returns job, second returns None

        self.scheduler.initialize(mock_bot)
        self.scheduler.start()

        user_id = "test_user_123"
        cron_expr = "0 7 * * *"

        # Add schedule first (mocked)
        self.scheduler.add_user_schedule(user_id, cron_expr)

        # Update to disable
        result = self.scheduler.update_user_schedule(user_id, "关闭")

        assert result is True
        mock_scheduler_instance.remove_job.assert_called_once()


class TestGlobalSchedulerAPI:
    """Test the global scheduler API functions."""

    def teardown_method(self):
        """Cleanup after each test method."""
        shutdown_scheduler()

    def test_get_scheduler_singleton(self):
        """Test that get_scheduler returns the same instance."""
        scheduler1 = get_scheduler()
        scheduler2 = get_scheduler()

        assert scheduler1 is scheduler2
        assert isinstance(scheduler1, PaperDigestScheduler)

    @patch('src.scheduler.default_config')
    @patch('src.scheduler.AsyncIOScheduler')
    def test_start_shutdown_scheduler(self, mock_scheduler_class, mock_config):
        """Test the global start/shutdown functions."""
        mock_config.dsn = "sqlite:///:memory:"
        mock_bot = Mock(spec=Application)

        # Mock the scheduler instance
        mock_scheduler_instance = Mock()
        mock_scheduler_instance.running = True
        mock_scheduler_class.return_value = mock_scheduler_instance

        # Test starting
        with patch('src.scheduler.PaperDigestScheduler.load_all_user_schedules'):
            start_scheduler(mock_bot)
            assert is_scheduler_running()

        # Test shutdown
        shutdown_scheduler()
        assert not is_scheduler_running()

    @patch('src.scheduler.default_config')
    @patch('src.scheduler.UserSetting')
    @patch('src.scheduler.AsyncIOScheduler')
    def test_sync_user_schedule_from_settings(self, mock_scheduler_class, mock_user_setting, mock_config):
        """Test syncing user schedule from database settings."""
        mock_config.dsn = "sqlite:///:memory:"
        # Mock user setting
        mock_user = Mock()
        mock_user.cron = "0 7 * * *"
        mock_user_setting.get_by_id.return_value = mock_user

        # Mock the scheduler instance
        mock_scheduler_instance = Mock()
        mock_scheduler_instance.running = True
        mock_scheduler_class.return_value = mock_scheduler_instance

        mock_bot = Mock(spec=Application)
        with patch('src.scheduler.PaperDigestScheduler.load_all_user_schedules'):
            start_scheduler(mock_bot)

        result = sync_user_schedule_from_settings("test_user")

        assert result is True
        mock_user_setting.get_by_id.assert_called_once_with("test_user")


@pytest.mark.asyncio
class TestScheduledExecution:
    """Test the scheduled job execution functionality."""

    def setup_method(self):
        """Setup for execution tests."""
        self.scheduler = PaperDigestScheduler()

    def teardown_method(self):
        """Cleanup after execution tests."""
        if self.scheduler.scheduler is not None:
            self.scheduler.shutdown()

    async def test_execute_scheduled_recommendation_no_bot(self):
        """Test execution when bot application is not available."""
        # Clear bot application
        self.scheduler.bot_application = None

        # Should not crash, just log error
        await self.scheduler.execute_scheduled_recommendation("test_user")

        # No assertions needed, just verify it doesn't crash

    @patch('src.scheduler.UserSetting')
    async def test_execute_scheduled_recommendation_no_user(self, mock_user_setting):
        """Test execution when user settings are not found."""
        mock_user_setting.get_by_id.return_value = None

        mock_bot = Mock(spec=Application)
        self.scheduler.bot_application = mock_bot

        await self.scheduler.execute_scheduled_recommendation("test_user")

        # Should have tried to remove the schedule
        mock_user_setting.get_by_id.assert_called_once_with("test_user")

    @patch('src.scheduler.UserSetting')
    @patch('src.scheduler.request_recommendations')
    async def test_execute_scheduled_recommendation_success(self, mock_request_recommendations, mock_user_setting):
        """Test successful execution of scheduled recommendation."""
        # Mock user setting
        mock_user = Mock()
        mock_user.cron = "0 7 * * *"
        mock_user.pat = "test_pat"
        mock_user.github_id = "test_user"
        mock_user.repo_name = "test_repo"
        mock_user_setting.get_by_id.return_value = mock_user

        # Mock recommendations
        import polars as pl
        mock_df = pl.DataFrame({"id": ["paper1", "paper2"], "title": ["Title 1", "Title 2"]})
        mock_request_recommendations.return_value = mock_df

        # Mock bot
        mock_bot = Mock(spec=Application)
        mock_bot.bot = AsyncMock()
        self.scheduler.bot_application = mock_bot

        # Mock render function
        with patch('src.scheduler.render_summary_tg') as mock_render:
            mock_render.return_value = {"paper1": "Summary 1", "paper2": "Summary 2"}

            await self.scheduler.execute_scheduled_recommendation("123456789")

            # Verify bot messages were sent
            assert mock_bot.bot.send_message.call_count >= 3  # Header + 2 recommendations
            mock_request_recommendations.assert_called_once_with("123456789")

    @patch('src.scheduler.UserSetting')
    @patch('src.scheduler.request_recommendations')
    async def test_execute_scheduled_recommendation_no_recommendations(self, mock_request_recommendations, mock_user_setting):
        """Test execution when no recommendations are available."""
        # Mock user setting
        mock_user = Mock()
        mock_user.cron = "0 7 * * *"
        mock_user.pat = "test_pat"
        mock_user.github_id = "test_user"
        mock_user.repo_name = "test_repo"
        mock_user_setting.get_by_id.return_value = mock_user

        # Mock empty recommendations
        import polars as pl
        mock_df = pl.DataFrame({"id": [], "title": []})
        mock_request_recommendations.return_value = mock_df

        # Mock bot
        mock_bot = Mock(spec=Application)
        mock_bot.bot = AsyncMock()
        self.scheduler.bot_application = mock_bot

        await self.scheduler.execute_scheduled_recommendation("123456789")

        # Verify no-recommendations message was sent
        mock_bot.bot.send_message.assert_called_once()
        call_args = mock_bot.bot.send_message.call_args
        assert "目前没有新的论文推荐" in call_args[1]['text']


if __name__ == "__main__":
    pytest.main([__file__])
