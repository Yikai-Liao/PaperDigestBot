from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from .base import BaseModel
from src.db import db

class ReactionRecord(BaseModel):
    """
    反应记录模型类
    用于记录用户对论文消息的反应（点赞、点踩等）
    """
    __tablename__ = 'reaction_record'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)  # 自增主键
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # Telegram 用户 ID
    message_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # Telegram 消息 ID
    arxiv_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # arXiv 论文 ID
    emoji: Mapped[str] = mapped_column(String(10), nullable=False)  # 反应表情
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 记录创建时间
    
    @classmethod
    def create(cls, user_id: str, message_id: str, arxiv_id: str, emoji: str) -> 'ReactionRecord':
        """
        创建新的反应记录
        
        Args:
            user_id: Telegram 用户 ID
            message_id: Telegram 消息 ID
            arxiv_id: arXiv 论文 ID
            emoji: 反应表情
            
        Returns:
            ReactionRecord: 新创建的反应记录对象
        """
        record = cls(
            user_id=user_id,
            message_id=message_id,
            arxiv_id=arxiv_id,
            emoji=emoji
        )
        record.save()
        return record
    
    @classmethod
    def get_by_message_and_user(cls, message_id: str, user_id: str) -> Optional['ReactionRecord']:
        """
        根据消息 ID 和用户 ID 获取记录
        
        Args:
            message_id: Telegram 消息 ID
            user_id: Telegram 用户 ID
            
        Returns:
            Optional[ReactionRecord]: 找到的记录或 None
        """
        with db.session() as session:
            return session.query(cls).filter_by(message_id=message_id, user_id=user_id).first()
    
    @classmethod
    def get_by_message_and_user_and_emoji(cls, message_id: str, user_id: str, emoji: str) -> Optional['ReactionRecord']:
        """
        根据消息 ID、用户 ID 和表情获取记录
        
        Args:
            message_id: Telegram 消息 ID
            user_id: Telegram 用户 ID
            emoji: 反应表情
            
        Returns:
            Optional[ReactionRecord]: 找到的记录或 None
        """
        with db.session() as session:
            return session.query(cls).filter_by(message_id=message_id, user_id=user_id, emoji=emoji).first()
    
    @classmethod
    def get_by_arxiv_id(cls, arxiv_id: str) -> list['ReactionRecord']:
        """
        根据 arXiv ID 获取所有相关记录
        
        Args:
            arxiv_id: arXiv 论文 ID
            
        Returns:
            list[ReactionRecord]: 相关记录列表
        """
        with db.session() as session:
            return session.query(cls).filter_by(arxiv_id=arxiv_id).all()
    
    @classmethod
    def get_by_user(cls, user_id: str) -> list['ReactionRecord']:
        """
        获取用户的所有反应记录
        
        Args:
            user_id: Telegram 用户 ID
            
        Returns:
            list[ReactionRecord]: 用户的反应记录列表
        """
        with db.session() as session:
            return session.query(cls).filter_by(user_id=user_id).all() 