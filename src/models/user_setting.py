"""
用户设置模型
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text, and_
from sqlalchemy.orm import Mapped, mapped_column

from src.db import db
from src.models.base import BaseModel


class UserSetting(BaseModel):
    """
    用户设置模型类
    用于存储用户的个性化设置
    """

    __tablename__ = "user_setting"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # Telegram 用户 ID
    github_id: Mapped[str | None] = mapped_column(String(50), nullable=True)  # GitHub 用户名
    pat: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # GitHub Personal Access Token
    github_pat: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )  # Encrypted GitHub Personal Access Token
    repo_name: Mapped[str | None] = mapped_column(String(100), nullable=True)  # GitHub 仓库名
    repo_url: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )  # GitHub repository URL
    timezone: Mapped[str | None] = mapped_column(String(50), nullable=True)  # User timezone
    cron: Mapped[str | None] = mapped_column(Text, nullable=True)  # Cron 表达式 (UTC)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 创建时间
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )  # 更新时间

    def __init__(self, **kwargs):
        """初始化模型实例"""
        # 确保 id 是字符串类型
        if "id" in kwargs:
            kwargs["id"] = str(kwargs["id"])
        super().__init__(**kwargs)

    @classmethod
    def get_by_user_id(cls, user_id: str) -> Optional["UserSetting"]:
        """
        根据用户 ID 获取设置

        Args:
            user_id: Telegram 用户 ID

        Returns:
            Optional[UserSetting]: 用户设置对象或 None
        """
        with db.session() as session:
            return session.query(cls).filter_by(id=str(user_id)).first()

    @classmethod
    def create_or_update(cls, user_id: str, **kwargs) -> "UserSetting":
        """
        创建或更新用户设置

        Args:
            user_id: Telegram 用户 ID
            **kwargs: 要更新的字段和值

        Returns:
            UserSetting: 更新后的用户设置对象
        """
        with db.session() as session:
            setting = session.query(cls).filter_by(id=str(user_id)).first()
            if not setting:
                setting = cls(id=str(user_id))

            for key, value in kwargs.items():
                if hasattr(setting, key):
                    setattr(setting, key, value)

            session.add(setting)
            session.commit()
            return setting

    def to_dict(self) -> dict:
        """
        转换为字典

        Returns:
            dict: 包含所有字段的字典
        """
        return {
            "id": self.id,
            "github_id": self.github_id,
            "pat": self.pat,
            "repo_name": self.repo_name,
            "cron": self.cron,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def get_by_id(cls, user_id: str) -> Optional["UserSetting"]:
        """
        根据用户 ID 获取设置（与 get_by_user_id 相同）

        Args:
            user_id: Telegram 用户 ID

        Returns:
            Optional[UserSetting]: 用户设置对象或 None
        """
        return cls.get_by_user_id(user_id)

    @classmethod
    def get_by_github_id(cls, github_id: str) -> Optional["UserSetting"]:
        """根据 GitHub ID 获取用户设置"""
        return cls.filter_one(github_id=github_id)

    @classmethod
    def get_by_repo(cls, repo_name: str) -> Optional["UserSetting"]:
        """根据仓库名获取用户设置"""
        return cls.filter_one(repo_name=repo_name)

    @classmethod
    def search_by_repo(cls, repo_pattern: str) -> list["UserSetting"]:
        """根据仓库名模糊搜索用户设置"""
        return cls.filter_by(repo_name=repo_pattern)

    @classmethod
    def get_active_users(cls) -> list["UserSetting"]:
        """获取所有活跃用户（已设置 PAT 的用户）"""
        with db.session() as session:
            return session.query(cls).filter(cls.pat.isnot(None)).all()

    @classmethod
    def update_pat(cls, user_id: str | int, pat: str) -> bool:
        """更新用户的 PAT"""
        with db.session() as session:
            user = session.query(cls).filter(cls.id == str(user_id)).first()
            if user:
                user.pat = pat
                session.commit()
                return True
            return False

    @classmethod
    def get_or_create(cls, user_id: str | int, **kwargs) -> "UserSetting":
        """获取或创建用户设置"""
        with db.session() as session:
            user = session.query(cls).filter(cls.id == str(user_id)).first()
            if not user:
                user = cls(id=str(user_id), **kwargs)
                session.add(user)
                session.commit()
            return user

    @classmethod
    def get_users_without_pat(cls) -> list["UserSetting"]:
        """获取所有未设置 PAT 的用户"""
        with db.session() as session:
            return session.query(cls).filter(cls.pat.is_(None)).all()

    @classmethod
    def get_users_without_repo(cls) -> list["UserSetting"]:
        """获取所有未设置仓库的用户"""
        with db.session() as session:
            return session.query(cls).filter(cls.repo_name.is_(None)).all()

    @classmethod
    def get_complete_users(cls) -> list["UserSetting"]:
        """获取所有设置完整的用户（所有字段都已设置）"""
        with db.session() as session:
            return (
                session.query(cls)
                .filter(
                    and_(
                        cls.pat.isnot(None),
                        cls.repo_name.isnot(None),
                        cls.cron.isnot(None),
                    )
                )
                .all()
            )

    def is_complete(self) -> bool:
        """检查用户设置是否完整"""
        return all(
            [
                self.pat is not None,
                self.repo_name is not None,
                self.cron is not None,
            ]
        )

    def get_missing_fields(self) -> list[str]:
        """获取未设置的字段列表"""
        missing = []
        if self.pat is None:
            missing.append("pat")
        if self.repo_name is None:
            missing.append("repo_name")
        if self.cron is None:
            missing.append("cron")
        return missing

    @classmethod
    def update_github_id(cls, user_id: str | int, github_id: str) -> bool:
        """更新用户的 GitHub ID"""
        with db.session() as session:
            user = session.query(cls).filter(cls.id == str(user_id)).first()
            if user:
                user.github_id = github_id
                session.commit()
                return True
            return False

    @classmethod
    def update_repo_name(cls, user_id: str | int, repo_name: str) -> bool:
        """更新用户的仓库名"""
        with db.session() as session:
            user = session.query(cls).filter(cls.id == str(user_id)).first()
            if user:
                user.repo_name = repo_name
                session.commit()
                return True
            return False

    @classmethod
    def get_all(cls) -> list["UserSetting"]:
        """获取所有用户设置"""
        with db.session() as session:
            return session.query(cls).all()
