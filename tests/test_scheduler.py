"""
Tests for the scheduler module
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestPaperDigestScheduler:
    """Test PaperDigestScheduler functionality"""

    @pytest.fixture
    def scheduler(self):
        """Create scheduler instance"""
        from src.scheduler import PaperDigestScheduler

        return PaperDigestScheduler()

    @pytest.fixture
    def mock_bot_application(self) -> Mock:
        """Mock Telegram bot application"""
        return Mock()

    @patch("src.scheduler.AsyncIOScheduler")
    @patch("src.scheduler.SQLAlchemyJobStore")
    def test_scheduler_initialization(
        self,
        mock_job_store: Mock,
        mock_scheduler_class: Mock,
        scheduler,
        mock_bot_application: Mock,
    ) -> None:
        """Test scheduler initialization"""
        mock_scheduler_instance = Mock()
        mock_scheduler_class.return_value = mock_scheduler_instance

        scheduler.initialize(mock_bot_application)

        # Verify scheduler was created with proper configuration
        mock_scheduler_class.assert_called_once()
        assert scheduler.bot_application == mock_bot_application
        assert scheduler.scheduler == mock_scheduler_instance

    def test_multiple_initialization_warning(self, scheduler, mock_bot_application: Mock) -> None:
        """Test that multiple initialization attempts log a warning"""
        with patch("src.scheduler.AsyncIOScheduler") as mock_scheduler_class:
            mock_scheduler_instance = Mock()
            mock_scheduler_class.return_value = mock_scheduler_instance

            # First initialization
            scheduler.initialize(mock_bot_application)

            # Second initialization should log warning
            with patch("src.scheduler.logger") as mock_logger:
                scheduler.initialize(mock_bot_application)
                mock_logger.warning.assert_called_once_with("Scheduler already initialized")

    def test_scheduler_not_initialized_operations(self, scheduler) -> None:
        """Test operations when scheduler is not initialized"""
        # Test operations on uninitialized scheduler
        assert scheduler.add_user_schedule("test_user", "0 9 * * *") is False
        assert scheduler.remove_user_schedule("test_user") is False

        # Start should raise error for uninitialized scheduler
        with pytest.raises(RuntimeError, match="Scheduler not initialized"):
            scheduler.start()

        # Shutdown should handle gracefully even if not initialized
        scheduler.shutdown()  # Should not raise error

    @patch("src.scheduler.AsyncIOScheduler")
    def test_preference_sync_job_initialization(
        self, mock_scheduler_class: Mock, scheduler, mock_bot_application: Mock
    ) -> None:
        """Test that preference sync job is added during initialization"""
        mock_scheduler_instance = Mock()
        mock_scheduler_class.return_value = mock_scheduler_instance

        scheduler.initialize(mock_bot_application)

        # Verify preference sync job was added
        add_job_calls = mock_scheduler_instance.add_job.call_args_list
        preference_job_call = None

        for call in add_job_calls:
            args, kwargs = call
            if kwargs.get("id") == "preference_sync_job":
                preference_job_call = call
                break

        assert preference_job_call is not None, "Preference sync job was not added"
        args, kwargs = preference_job_call
        assert kwargs["name"] == "Daily preference synchronization"
        assert kwargs["hour"] == 0  # UTC midnight
        assert kwargs["minute"] == 0

    @patch("src.scheduler.AsyncIOScheduler")
    def test_trigger_preference_sync(
        self, mock_scheduler_class: Mock, scheduler, mock_bot_application: Mock
    ) -> None:
        """Test manual triggering of preference sync"""
        mock_scheduler_instance = Mock()
        mock_scheduler_class.return_value = mock_scheduler_instance

        scheduler.initialize(mock_bot_application)

        # Test triggering preference sync
        result = scheduler.trigger_preference_sync()

        assert result is True

        # Verify manual preference sync job was added
        add_job_calls = mock_scheduler_instance.add_job.call_args_list
        manual_job_call = None

        for call in add_job_calls:
            args, kwargs = call
            if kwargs.get("id") == "manual_preference_sync":
                manual_job_call = call
                break

        assert manual_job_call is not None, "Manual preference sync job was not added"
        args, kwargs = manual_job_call
        assert kwargs["name"] == "Manual preference synchronization"

    def test_trigger_preference_sync_not_initialized(self, scheduler) -> None:
        """Test triggering preference sync when scheduler is not initialized"""
        result = scheduler.trigger_preference_sync()
        assert result is False


class TestPreferenceSyncFunction:
    """Test the execute_preference_sync function"""

    @patch("src.scheduler.PreferenceManager")
    @pytest.mark.asyncio
    async def test_execute_preference_sync_success(
        self, mock_preference_manager_class: Mock
    ) -> None:
        """Test successful preference synchronization execution"""
        from src.scheduler import execute_preference_sync

        # Mock preference manager
        mock_manager = Mock()
        mock_manager.sync_all_users_preferences.return_value = {
            "user1": True,
            "user2": True,
            "user3": False,
        }
        mock_preference_manager_class.return_value = mock_manager

        # Execute the function
        await execute_preference_sync()

        # Verify manager was created and called
        mock_preference_manager_class.assert_called_once()
        mock_manager.sync_all_users_preferences.assert_called_once_with(days_back=2)

    @patch("src.scheduler.PreferenceManager")
    @patch("src.scheduler.logger")
    @pytest.mark.asyncio
    async def test_execute_preference_sync_failure(
        self, mock_logger: Mock, mock_preference_manager_class: Mock
    ) -> None:
        """Test preference synchronization execution with failure"""
        from src.scheduler import execute_preference_sync

        # Mock preference manager to raise exception
        mock_preference_manager_class.side_effect = Exception("Sync failed")

        # Execute the function
        await execute_preference_sync()

        # Verify error was logged
        mock_logger.error.assert_called()
        error_calls = [
            call
            for call in mock_logger.error.call_args_list
            if "Error during preference synchronization" in str(call)
        ]
        assert len(error_calls) > 0


class TestSchedulerPreferenceIntegration:
    """Integration tests for scheduler preference functionality"""

    @patch("src.scheduler.trigger_preference_sync")
    def test_trigger_preference_sync_public_api(self, mock_trigger: Mock) -> None:
        """Test the public API for triggering preference sync"""
        from src.scheduler import trigger_preference_sync

        mock_trigger.return_value = True
        result = trigger_preference_sync()

        assert result is True
        mock_trigger.assert_called_once()
