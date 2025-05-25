from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, String, Text, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from src.db import db
from .base import BaseModel

class MessageRecord(BaseModel):
    """
    消息记录模型类
    用于记录用户或群组对论文的消息行为
    """
    __tablename__ = 'message_record'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)  # 自增主键
    group_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # Telegram 群组 ID
    user_id: Mapped[str] = mapped_column(String(32), nullable=False)  # Telegram 用户 ID
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Telegram 消息 ID
    arxiv_id: Mapped[str] = mapped_column(Text, nullable=False)  # arXiv 论文 ID
    repo_name: Mapped[str] = mapped_column(Text, nullable=False)  # GitHub 仓库名
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 创建时间
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # 更新时间
    
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
        # Save to database
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
    def get_by_context(cls, group_id: Optional[str], user_id: str, message_id: int) -> Optional['MessageRecord']:
        """
        根据群组ID、用户ID和消息ID组合获取记录
        这是更精确的查找方法，因为message_id在不同群组中可能重复
        
        Args:
            group_id: Telegram 群组 ID，私聊时为 None
            user_id: Telegram 用户 ID  
            message_id: Telegram 消息 ID
            
        Returns:
            Optional[MessageRecord]: 找到的记录或 None
        """
        with db.session() as session:
            return session.query(cls).filter(
                cls.group_id == group_id,
                cls.user_id == user_id,
                cls.message_id == message_id
            ).first()
    
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