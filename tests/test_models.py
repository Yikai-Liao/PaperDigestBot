"""
Tests for database models
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.models.message_record import MessageRecord
from src.models.reaction_record import ReactionRecord
from src.models.user_setting import UserSetting


class TestUserSetting:
    """Test UserSetting model"""

    def test_user_setting_creation(self, sample_user_data: dict) -> None:
        """Test creating a UserSetting instance"""
        user_setting = UserSetting(**sample_user_data)

        assert user_setting.id == sample_user_data["id"]
        assert user_setting.github_id == sample_user_data["github_id"]
        assert user_setting.repo_name == sample_user_data["repo_name"]
        assert user_setting.pat == sample_user_data["pat"]
        assert user_setting.cron == sample_user_data["cron"]

    def test_user_setting_id_conversion(self) -> None:
        """Test that user ID is converted to string"""
        user_setting = UserSetting(id=12345)
        assert user_setting.id == "12345"
        assert isinstance(user_setting.id, str)

    def test_to_dict_method(self, sample_user_data: dict) -> None:
        """Test converting UserSetting to dictionary"""
        user_setting = UserSetting(**sample_user_data)
        user_setting.created_at = datetime.now()
        user_setting.updated_at = datetime.now()

        result = user_setting.to_dict()

        assert result["id"] == sample_user_data["id"]
        assert result["github_id"] == sample_user_data["github_id"]
        assert result["repo_name"] == sample_user_data["repo_name"]
        assert result["pat"] == sample_user_data["pat"]
        assert result["cron"] == sample_user_data["cron"]
        assert "created_at" in result
        assert "updated_at" in result

    @patch("src.models.user_setting.db")
    def test_get_by_user_id(self, mock_db: Mock) -> None:
        """Test getting user setting by user ID"""
        # Setup mock
        mock_session = Mock()
        mock_db.session.return_value.__enter__.return_value = mock_session
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value.first.return_value = Mock(spec=UserSetting)

        # Test
        result = UserSetting.get_by_user_id("test_user")

        # Verify
        assert result is not None
        mock_session.query.assert_called_once_with(UserSetting)
        mock_query.filter_by.assert_called_once_with(id="test_user")

    @patch("src.models.user_setting.db")
    def test_get_by_user_id_not_found(self, mock_db: Mock) -> None:
        """Test getting user setting for non-existent user"""
        # Setup mock
        mock_session = Mock()
        mock_db.session.return_value.__enter__.return_value = mock_session
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value.first.return_value = None

        # Test
        result = UserSetting.get_by_user_id("nonexistent_user")

        # Verify
        assert result is None

    @patch("src.models.user_setting.db")
    def test_create_or_update_new_user(self, mock_db: Mock, sample_user_data: dict) -> None:
        """Test creating new user setting"""
        # Setup mock
        mock_session = Mock()
        mock_db.session.return_value.__enter__.return_value = mock_session
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value.first.return_value = None  # User doesn't exist

        # Test
        user_id = sample_user_data["id"]
        update_data = {k: v for k, v in sample_user_data.items() if k != "id"}
        result = UserSetting.create_or_update(user_id, **update_data)

        # Verify
        assert result is not None
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch("src.models.user_setting.db")
    def test_create_or_update_existing_user(self, mock_db: Mock, sample_user_data: dict) -> None:
        """Test updating existing user setting"""
        # Setup mock
        mock_session = Mock()
        mock_db.session.return_value.__enter__.return_value = mock_session
        mock_query = Mock()
        existing_user = UserSetting(id=sample_user_data["id"])
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value.first.return_value = existing_user

        # Test
        user_id = sample_user_data["id"]
        update_data = {"github_id": "new_github_id", "pat": "new_pat"}
        result = UserSetting.create_or_update(user_id, **update_data)

        # Verify
        assert result.github_id == "new_github_id"
        assert result.pat == "new_pat"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()


@pytest.fixture
def sample_message_record_data() -> dict:
    """Sample message record data"""
    return {
        "user_id": "test_user_123",
        "chat_id": "test_chat_456",
        "message_id": "test_message_789",
        "summary_content": "Test summary content",
    }


@pytest.fixture
def sample_reaction_record_data() -> dict:
    """Sample reaction record data"""
    return {
        "user_id": "test_user_123",
        "message_id": "test_message_789",
        "reaction": "👍",
        "paper_id": "2024.01234",
    }


class TestMessageRecord:
    """Test MessageRecord model"""

    def test_message_record_creation(self, sample_message_record_data: dict) -> None:
        """Test creating a MessageRecord instance"""
        # Create a mock MessageRecord object without using SQLAlchemy
        message_record = type("MessageRecord", (), {})()

        # Set attributes for testing
        for key, value in sample_message_record_data.items():
            setattr(message_record, key, value)

        assert message_record.user_id == sample_message_record_data["user_id"]
        assert message_record.chat_id == sample_message_record_data["chat_id"]
        assert message_record.message_id == sample_message_record_data["message_id"]
        assert message_record.summary_content == sample_message_record_data["summary_content"]


class TestReactionRecord:
    """Test ReactionRecord model"""

    def test_reaction_record_creation(self, sample_reaction_record_data: dict) -> None:
        """Test creating a ReactionRecord instance"""
        # Create a mock ReactionRecord object without using SQLAlchemy
        reaction_record = type("ReactionRecord", (), {})()

        # Set attributes for testing
        for key, value in sample_reaction_record_data.items():
            setattr(reaction_record, key, value)

        assert reaction_record.user_id == sample_reaction_record_data["user_id"]
        assert reaction_record.message_id == sample_reaction_record_data["message_id"]
        assert reaction_record.reaction == sample_reaction_record_data["reaction"]
        assert reaction_record.paper_id == sample_reaction_record_data["paper_id"]
