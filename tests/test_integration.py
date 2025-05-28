"""
Integration tests for PaperDigestBot
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from telegram import Update, User, Message, Chat

from src.dispatcher import RecommendationService, SettingsParser
from src.models.user_setting import UserSetting


@pytest.mark.integration
class TestSettingsIntegration:
    """Integration tests for settings management"""

    @pytest.mark.asyncio
    async def test_full_settings_workflow(self, db_session, sample_settings_text: str) -> None:
        """Test complete settings parsing and storage workflow"""
        user_id = "integration_test_user"

        # Parse settings
        parsed_settings = SettingsParser.parse_settings(sample_settings_text)

        # Verify parsing worked
        assert parsed_settings["github_id"] == "testuser"
        assert parsed_settings["repo_name"] == "test-repo"
        assert parsed_settings["pat"] == "test_pat_token"
        assert parsed_settings["cron"] == "0 9 * * *"
        assert parsed_settings["timezone"] == "Asia/Shanghai"

        # Create user setting with parsed data
        with patch("src.models.user_setting.db", db_session):
            user_setting = UserSetting.create_or_update(
                user_id,
                github_id=parsed_settings["github_id"],
                repo_name=parsed_settings["repo_name"],
                pat=parsed_settings["pat"],
                cron=parsed_settings["cron"],
            )

            # Verify user setting was created
            assert user_setting.id == user_id
            assert user_setting.github_id == parsed_settings["github_id"]
            assert user_setting.repo_name == parsed_settings["repo_name"]
            assert user_setting.pat == parsed_settings["pat"]
            assert user_setting.cron == parsed_settings["cron"]

    @pytest.mark.asyncio
    async def test_recommendation_service_integration(
        self, db_session, sample_user_data: dict
    ) -> None:
        """Test integration of recommendation service with database"""
        user_id = sample_user_data["id"]

        # Create user setting in database
        with patch("src.models.user_setting.db", db_session):
            UserSetting.create_or_update(user_id, **sample_user_data)

            # Create recommendation service
            service = RecommendationService()

            # Mock the test data method to avoid file system dependencies
            with patch.object(service, "_get_test_data") as mock_get_test_data:
                mock_get_test_data.return_value = Mock()  # Mock DataFrame

                # Request recommendations
                result = await service.request_recommendations(user_id)

                # Verify recommendation was generated
                assert result is not None
                mock_get_test_data.assert_called_once()


@pytest.mark.integration
class TestSchedulerIntegration:
    """Integration tests for scheduler functionality"""

    @pytest.mark.asyncio
    async def test_scheduler_with_user_settings(self, db_session, sample_user_data: dict) -> None:
        """Test scheduler integration with user settings"""
        from src.scheduler import PaperDigestScheduler

        user_id = sample_user_data["id"]

        # Create user setting with cron schedule
        with patch("src.models.user_setting.db", db_session):
            UserSetting.create_or_update(user_id, **sample_user_data)

            # Create and initialize scheduler
            scheduler = PaperDigestScheduler()

            with patch("src.scheduler.AsyncIOScheduler") as mock_scheduler_class:
                mock_scheduler_instance = Mock()
                mock_scheduler_class.return_value = mock_scheduler_instance

                scheduler.initialize()

                # Add user schedule
                with patch("src.scheduler.UserSetting") as mock_user_setting:
                    mock_user = Mock()
                    mock_user.id = user_id
                    mock_user.cron = sample_user_data["cron"]
                    mock_user_setting.get_by_id.return_value = mock_user

                    result = scheduler.add_user_schedule(user_id, sample_user_data["cron"])

                    # Verify schedule was added
                    assert result is True
                    # Should be called twice: once for preference sync job, once for user job
                    assert mock_scheduler_instance.add_job.call_count == 2


@pytest.mark.integration
class TestTelegramBotIntegration:
    """Integration tests for Telegram bot commands"""

    @pytest.mark.asyncio
    async def test_sync_command_flow(self, db_session) -> None:
        """Test sync command integration flow"""
        from src.bot.tg import sync_preferences, process_sync_background

        # Create mock user setting
        user_id = "123456789"  # Use numeric string for Telegram user ID
        user_setting = UserSetting(
            id=user_id,
            github_id="testuser",
            repo_name="test-repo",
            repo_url="https://github.com/testuser/test-repo",
            github_pat="encrypted_test_pat",
        )
        
        with patch("src.models.user_setting.UserSetting.get_by_id", return_value=user_setting):
            with patch("src.preference.PreferenceManager.sync_user_preferences", return_value=True) as mock_sync:
                # Create mock update and context
                mock_user = Mock()
                mock_user.id = int(user_id)
                
                mock_message = Mock()
                mock_message.reply_text = AsyncMock(return_value=Mock(message_id=123))
                
                mock_chat = Mock()
                mock_chat.id = int(user_id)
                
                mock_update = Mock()
                mock_update.effective_user = mock_user
                mock_update.effective_chat = mock_chat
                mock_update.message = mock_message
                
                mock_bot = Mock()
                mock_bot.edit_message_text = AsyncMock()
                
                mock_context = Mock()
                mock_context.bot = mock_bot
                
                # Test sync command
                await sync_preferences(mock_update, mock_context)
                
                # Verify initial message was sent
                mock_message.reply_text.assert_called_once_with("🔄 正在同步您的偏好数据，请稍候...")

    @pytest.mark.asyncio
    async def test_sync_command_no_settings(self, db_session) -> None:
        """Test sync command with no user settings"""
        from src.bot.tg import process_sync_background

        user_id = "987654321"  # Use numeric string for Telegram user ID
        
        with patch("src.models.user_setting.UserSetting.get_by_id", return_value=None):
            mock_bot = Mock()
            mock_bot.edit_message_text = AsyncMock()
            
            mock_context = Mock()
            mock_context.bot = mock_bot
            
            # Test background processing
            await process_sync_background(
                user_id=user_id,
                chat_id=123,
                message_id=456,
                context=mock_context
            )
            
            # Verify error message was sent
            mock_bot.edit_message_text.assert_called_once()
            call_args = mock_bot.edit_message_text.call_args
            assert "您还没有进行任何设置" in call_args[1]["text"]


@pytest.mark.integration
@pytest.mark.slow
class TestFullWorkflow:
    """Test complete workflow integration"""

    @pytest.mark.asyncio
    async def test_complete_user_onboarding_workflow(
        self, db_session, sample_settings_text: str
    ) -> None:
        """Test complete user onboarding and recommendation workflow"""
        user_id = "workflow_test_user"

        # Step 1: Parse user settings
        parsed_settings = SettingsParser.parse_settings(sample_settings_text)

        # Step 2: Store user settings
        with patch("src.models.user_setting.db", db_session):
            user_setting = UserSetting.create_or_update(
                user_id,
                github_id=parsed_settings["github_id"],
                repo_name=parsed_settings["repo_name"],
                pat=parsed_settings["pat"],
                cron=parsed_settings["cron"],
            )

            # Step 3: Add user to scheduler
            from src.scheduler import PaperDigestScheduler

            scheduler = PaperDigestScheduler()

            with patch("src.scheduler.AsyncIOScheduler") as mock_scheduler_class:
                mock_scheduler_instance = Mock()
                mock_scheduler_class.return_value = mock_scheduler_instance

                scheduler.initialize()

                # Mock UserSetting.get_by_id to return our created user
                with patch("src.scheduler.UserSetting") as mock_user_setting:
                    mock_user_setting.get_by_id.return_value = user_setting

                    result = scheduler.add_user_schedule(user_id, parsed_settings["cron"])
                    assert result is True

            # Step 4: Generate recommendations
            service = RecommendationService()

            with patch.object(service, "_get_test_data") as mock_get_test_data:
                mock_get_test_data.return_value = Mock()

                # Mock UserSetting.get_by_id for recommendation service
                with patch("src.dispatcher.UserSetting") as mock_user_setting:
                    mock_user_setting.get_by_id.return_value = user_setting

                    recommendations = await service.request_recommendations(user_id)
                    assert recommendations is not None

        # Verify complete workflow succeeded
        assert user_setting.id == user_id
        assert user_setting.github_id == parsed_settings["github_id"]
        assert user_setting.repo_name == parsed_settings["repo_name"]
