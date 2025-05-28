"""
测试数据库结构与模型定义的一致性
"""

from unittest.mock import patch

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from src.db import db
from src.models.message_record import MessageRecord
from src.models.reaction_record import ReactionRecord
from src.models.user_setting import UserSetting


@pytest.mark.integration
class TestDatabaseSchema:
    """测试数据库结构"""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        """测试前初始化数据库连接"""
        self.db = db_session

    def test_user_setting_table_exists(self):
        """测试user_setting表是否存在且字段正确"""
        engine: Engine = self.db.engine
        inspector = inspect(engine)

        # 检查表是否存在
        assert "user_setting" in inspector.get_table_names()

        # 检查字段
        columns = {col["name"]: col for col in inspector.get_columns("user_setting")}

        expected_columns = {
            "id",
            "github_id",
            "pat",
            "github_pat",
            "repo_name",
            "repo_url",
            "timezone",
            "cron",
            "created_at",
            "updated_at",
        }
        actual_columns = set(columns.keys())

        assert (
            expected_columns == actual_columns
        ), f"字段不匹配: 预期 {expected_columns}, 实际 {actual_columns}"

    def test_message_record_table_exists(self):
        """测试message_record表是否存在且字段正确"""
        engine: Engine = self.db.engine
        inspector = inspect(engine)

        # 检查表是否存在
        assert "message_record" in inspector.get_table_names()

        # 检查字段
        columns = {col["name"]: col for col in inspector.get_columns("message_record")}

        expected_columns = {
            "id",
            "group_id",
            "user_id",
            "message_id",
            "arxiv_id",
            "repo_name",
            "created_at",
            "updated_at",
        }
        actual_columns = set(columns.keys())

        assert (
            expected_columns == actual_columns
        ), f"字段不匹配: 预期 {expected_columns}, 实际 {actual_columns}"

    def test_reaction_record_table_exists(self):
        """测试reaction_record表是否存在且字段正确"""
        engine: Engine = self.db.engine
        inspector = inspect(engine)

        # 检查表是否存在
        assert "reaction_record" in inspector.get_table_names()

        # 检查字段
        columns = {col["name"]: col for col in inspector.get_columns("reaction_record")}

        expected_columns = {
            "id",
            "group_id",
            "user_id",
            "message_id",
            "arxiv_id",
            "emoji",
            "created_at",
            "updated_at",
        }
        actual_columns = set(columns.keys())

        assert (
            expected_columns == actual_columns
        ), f"字段不匹配: 预期 {expected_columns}, 实际 {actual_columns}"

    def test_user_setting_model_crud(self):
        """测试UserSetting模型的CRUD操作"""
        # 使用测试数据库会话
        with patch("src.models.user_setting.db", self.db):
            # 创建用户设置
            user_setting = UserSetting.create_or_update(
                user_id="test_user_123",
                github_id="test_github",
                pat="test_pat",
                repo_name="test/repo",
                cron="0 0 * * *",
            )

            assert user_setting.id == "test_user_123"
            assert user_setting.github_id == "test_github"
            assert user_setting.cron == "0 0 * * *"

            # 测试查询
            found_user = UserSetting.get_by_user_id("test_user_123")
            assert found_user is not None
            assert found_user.github_id == "test_github"

            # 测试更新
            updated_user = UserSetting.create_or_update(
                user_id="test_user_123", github_id="updated_github"
            )
            assert updated_user.github_id == "updated_github"
            assert updated_user.cron == "0 0 * * *"  # 原有字段应该保持

    def test_no_obsolete_fields_in_database(self):
        """确保数据库中没有过时的字段"""
        engine: Engine = self.db.engine
        inspector = inspect(engine)

        # 检查user_setting表中不应该存在的过时字段
        columns = {col["name"] for col in inspector.get_columns("user_setting")}
        obsolete_fields = {"frequency", "domain"}

        found_obsolete = obsolete_fields.intersection(columns)
        assert not found_obsolete, f"发现过时字段: {found_obsolete}"

    def test_table_constraints(self):
        """测试表约束"""
        engine: Engine = self.db.engine
        inspector = inspect(engine)

        # 检查主键约束
        user_setting_pk = inspector.get_pk_constraint("user_setting")
        assert user_setting_pk["constrained_columns"] == ["id"]

        message_record_pk = inspector.get_pk_constraint("message_record")
        assert message_record_pk["constrained_columns"] == ["id"]

        reaction_record_pk = inspector.get_pk_constraint("reaction_record")
        assert reaction_record_pk["constrained_columns"] == ["id"]

    def test_user_setting_complete_check(self):
        """测试用户设置完整性检查"""
        # 不完整的用户设置
        incomplete_user = UserSetting(id="incomplete", github_id="test")
        assert not incomplete_user.is_complete()

        missing_fields = incomplete_user.get_missing_fields()
        assert "pat" in missing_fields
        assert "repo_name" in missing_fields
        assert "cron" in missing_fields

        # 完整的用户设置
        complete_user = UserSetting(
            id="complete", github_id="test", pat="test_pat", repo_name="test/repo", cron="0 0 * * *"
        )
        assert complete_user.is_complete()
        assert complete_user.get_missing_fields() == []
