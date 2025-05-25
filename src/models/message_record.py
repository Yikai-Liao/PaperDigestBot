from datetime import datetime
from typing import Optional
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column
from .base import BaseModel
from src.db import db

class MessageRecord(BaseModel):
    """
    消息记录模型类
    用于记录用户或群组对论文的消息行为
    """
    __tablename__ = 'message_record'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)  # 自增主键
    group_id: Mapped[Optional[str]] = mapped_column(nullable=True)  # Telegram 群组 ID
    user_id: Mapped[str] = mapped_column()  # Telegram 用户 ID
    message_id: Mapped[int] = mapped_column()  # Telegram 消息 ID
    arxiv_id: Mapped[str] = mapped_column()  # arXiv 论文 ID
    repo_name: Mapped[str] = mapped_column()  # GitHub 仓库名
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)  # 记录创建时间
    
    @classmethod
    def create(cls, group_id: Optional[str], user_id: str, message_id: int, 
               arxiv_id: str, repo_name: str) -> 'MessageRecord':
        """
        创建新的消息记录
        
        Args:
            group_id: Telegram 群组 ID，可以为 None
            user_id: Telegram 用户 ID
            message_id: Telegram 消息 ID
            arxiv_id: arXiv 论文 ID
            repo_name: GitHub 仓库名
            
        Returns:
            MessageRecord: 新创建的消息记录对象
        """
        record = cls(
            group_id=group_id,
            user_id=user_id,
            message_id=message_id,
            arxiv_id=arxiv_id,
            repo_name=repo_name
        )
        record.save()
        return record
    
    @classmethod
    def get_by_message_id(cls, message_id: int) -> Optional['MessageRecord']:
        """
        根据消息 ID 获取记录
        
        Args:
            message_id: Telegram 消息 ID
            
        Returns:
            Optional[MessageRecord]: 找到的记录或 None
        """
        with db.session() as session:
            return session.query(cls).filter(cls.message_id == message_id).first()
    
    @classmethod
    def get_by_arxiv_id(cls, arxiv_id: str) -> list['MessageRecord']:
        """
        根据 arXiv ID 获取所有相关记录
        
        Args:
            arxiv_id: arXiv 论文 ID
            
        Returns:
            list[MessageRecord]: 相关记录列表
        """
        with db.session() as session:
            return session.query(cls).filter(cls.arxiv_id == arxiv_id).all()
    
    @classmethod
    def get_by_user(cls, user_id: str) -> list['MessageRecord']:
        """
        获取用户的所有消息记录
        
        Args:
            user_id: Telegram 用户 ID
            
        Returns:
            list[MessageRecord]: 用户的消息记录列表
        """
        with db.session() as session:
            return session.query(cls).filter(cls.user_id == user_id).all()
    
    @classmethod
    def get_by_group(cls, group_id: str) -> list['MessageRecord']:
        """
        获取群组的所有消息记录
        
        Args:
            group_id: Telegram 群组 ID
            
        Returns:
            list[MessageRecord]: 群组的消息记录列表
        """
        with db.session() as session:
            return session.query(cls).filter(cls.group_id == group_id).all() 