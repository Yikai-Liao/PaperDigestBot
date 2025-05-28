"""
Tests for the dispatcher module
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.dispatcher import (
    RecommendationService,
    SettingsParser,
    parse_settings,
    request_recommendations,
)


class TestSettingsParser:
    """Test settings parser functionality"""

    def test_parse_valid_settings(self, sample_settings_text: str) -> None:
        """Test parsing valid settings text"""
        result = SettingsParser.parse_settings(sample_settings_text)

        assert result["github_id"] == "testuser"
        assert result["repo_name"] == "test-repo"
        assert result["pat"] == "test_pat_token"
        assert result["cron"] == "0 9 * * *"
        assert result["timezone"] == "Asia/Shanghai"

    def test_parse_repo_setting(self) -> None:
        """Test parsing repository setting"""
        settings_text = "repo:username/repository"
        result = SettingsParser.parse_settings(settings_text)

        assert result["github_id"] == "username"
        assert result["repo_name"] == "repository"

    def test_parse_pat_setting(self) -> None:
        """Test parsing PAT setting"""
        settings_text = "pat:github_pat_token_123"
        result = SettingsParser.parse_settings(settings_text)

        assert result["pat"] == "github_pat_token_123"

    def test_parse_cron_setting(self) -> None:
        """Test parsing cron setting"""
        settings_text = "cron:0 9 * * *"
        result = SettingsParser.parse_settings(settings_text)

        assert result["cron"] == "0 9 * * *"

    def test_parse_cron_disable(self) -> None:
        """Test parsing cron disable setting"""
        settings_text = "cron:关闭"
        result = SettingsParser.parse_settings(settings_text)

        assert result["cron"] == "关闭"

    def test_parse_timezone_setting(self) -> None:
        """Test parsing timezone setting"""
        settings_text = "timezone:America/New_York"
        result = SettingsParser.parse_settings(settings_text)

        assert result["timezone"] == "America/New_York"

    def test_parse_multiple_settings(self) -> None:
        """Test parsing multiple settings"""
        settings_text = "repo:user/repo;cron:0 8 * * *"
        result = SettingsParser.parse_settings(settings_text)

        assert result["github_id"] == "user"
        assert result["repo_name"] == "repo"
        assert result["cron"] == "0 8 * * *"

    def test_parse_empty_settings(self) -> None:
        """Test parsing empty settings"""
        result = SettingsParser.parse_settings("")
        assert result == {}

    def test_parse_settings_with_spaces(self) -> None:
        """Test parsing settings with extra spaces"""
        settings_text = " repo : user/repo ; pat : token123 "
        result = SettingsParser.parse_settings(settings_text)

        assert result["github_id"] == "user"
        assert result["repo_name"] == "repo"
        assert result["pat"] == "token123"

    def test_invalid_repo_format(self) -> None:
        """Test invalid repository format"""
        with pytest.raises(ValueError, match="Repo 格式必须为 USER/REPO"):
            SettingsParser.parse_settings("repo:invalid_format")

    def test_empty_pat(self) -> None:
        """Test empty PAT value"""
        with pytest.raises(ValueError, match="PAT 不能为空"):
            SettingsParser.parse_settings("pat:")

    def test_empty_repo(self) -> None:
        """Test empty repository value"""
        with pytest.raises(ValueError, match="Repo 不能为空"):
            SettingsParser.parse_settings("repo:")

    def test_invalid_cron_format(self) -> None:
        """Test invalid cron format"""
        with pytest.raises(ValueError, match="无效的 Cron 表达式格式"):
            SettingsParser.parse_settings("cron:invalid")

    def test_empty_cron(self) -> None:
        """Test empty cron value"""
        with pytest.raises(ValueError, match="Cron 表达式不能为空"):
            SettingsParser.parse_settings("cron:")

    def test_unknown_setting_key(self) -> None:
        """Test unknown setting key"""
        with pytest.raises(ValueError, match="未知的设置项"):
            SettingsParser.parse_settings("unknown:value")

    def test_malformed_setting_item(self) -> None:
        """Test malformed setting item"""
        with pytest.raises(ValueError, match="无法解析设置项"):
            SettingsParser.parse_settings("malformed_item_without_colon")

    def test_legacy_parse_settings_function(self, sample_settings_text: str) -> None:
        """Test the legacy parse_settings function"""
        result = parse_settings(sample_settings_text)

        assert result["github_id"] == "testuser"
        assert result["repo_name"] == "test-repo"
        assert result["pat"] == "test_pat_token"


class TestRecommendationService:
    """Test recommendation service functionality"""

    @pytest.fixture
    def mock_user_setting(self) -> Mock:
        """Mock user setting object"""
        user_setting = Mock()
        user_setting.pat = "test_pat"
        user_setting.github_id = "test_user"
        user_setting.repo_name = "test_repo"
        return user_setting

    @pytest.fixture
    def service(self) -> RecommendationService:
        """Create recommendation service instance"""
        return RecommendationService()

    @patch("src.dispatcher.UserSetting")
    @pytest.mark.asyncio
    async def test_successful_recommendation_request(
        self, mock_user_setting_class: Mock, service: RecommendationService, mock_user_setting: Mock
    ) -> None:
        """Test successful recommendation request"""
        # Mock UserSetting.get_by_id to return our mock user setting
        mock_user_setting_class.get_by_id.return_value = mock_user_setting

        # Mock the test data method to return a simple DataFrame
        with patch.object(service, "_get_test_data") as mock_get_test_data:
            mock_get_test_data.return_value = Mock()  # Mock DataFrame

            result = await service.request_recommendations("test_user")

            assert result is not None
            mock_user_setting_class.get_by_id.assert_called_once_with("test_user")

    @patch("src.dispatcher.UserSetting")
    @pytest.mark.asyncio
    async def test_user_not_found(
        self, mock_user_setting_class: Mock, service: RecommendationService
    ) -> None:
        """Test recommendation request for non-existent user"""
        mock_user_setting_class.get_by_id.return_value = None

        result = await service.request_recommendations("nonexistent_user")

        assert result is None

    @patch("src.dispatcher.UserSetting")
    @pytest.mark.asyncio
    async def test_user_missing_pat(
        self, mock_user_setting_class: Mock, service: RecommendationService
    ) -> None:
        """Test recommendation request for user missing PAT"""
        user_setting = Mock()
        user_setting.pat = None
        user_setting.github_id = "test_user"
        user_setting.repo_name = "test_repo"
        mock_user_setting_class.get_by_id.return_value = user_setting

        result = await service.request_recommendations("test_user")

        assert result is None

    @patch("src.dispatcher.UserSetting")
    @pytest.mark.asyncio
    async def test_user_missing_repo_info(
        self, mock_user_setting_class: Mock, service: RecommendationService
    ) -> None:
        """Test recommendation request for user missing repository information"""
        user_setting = Mock()
        user_setting.pat = "test_pat"
        user_setting.github_id = None
        user_setting.repo_name = "test_repo"
        mock_user_setting_class.get_by_id.return_value = user_setting

        result = await service.request_recommendations("test_user")

        assert result is None

    @patch("src.dispatcher.UserSetting")
    @pytest.mark.asyncio
    async def test_exception_handling(
        self, mock_user_setting_class: Mock, service: RecommendationService
    ) -> None:
        """Test exception handling in recommendation request"""
        mock_user_setting_class.get_by_id.side_effect = Exception("Database error")

        result = await service.request_recommendations("test_user")

        assert result is None

    @pytest.mark.asyncio
    async def test_legacy_request_recommendations_function(self) -> None:
        """Test the legacy request_recommendations function"""
        with patch("src.dispatcher.RecommendationService") as mock_service_class:
            mock_service = Mock()
            mock_service.request_recommendations = AsyncMock(return_value=Mock())
            mock_service_class.return_value = mock_service

            result = await request_recommendations("test_user")

            assert result is not None
            mock_service.request_recommendations.assert_called_once_with("test_user", None)
