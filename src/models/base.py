"""
基础模型类
提供通用的数据库操作方法
"""
from typing import Optional, Any, Dict, List, Union, Tuple, Type, TypeVar, Generic, ClassVar
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, ForeignKey, Table, MetaData, select, update, delete, and_, or_, text
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import Select
from datetime import datetime
from src.db import db
from loguru import logger

T = TypeVar('T', bound='BaseModel')

class BaseModel(DeclarativeBase):
    """基础模型类"""

    __abstract__ = True

    id = Column(String(32), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, **kwargs):
        """初始化模型实例"""
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def initialize(cls) -> None:
        """初始化数据库表"""
        try:
            cls.metadata.create_all(db.engine)
            logger.info(f"表 {cls.__tablename__} 创建成功")
        except Exception as e:
            logger.error(f"初始化表 {cls.__tablename__} 失败: {e}")
            raise

    @classmethod
    def get_by_id(cls, id: Union[str, int]) -> Optional[T]:
        """根据ID获取记录"""
        with db.session() as session:
            return session.query(cls).filter_by(id=str(id)).first()

    @classmethod
    def get_all(cls) -> List[T]:
        """获取所有记录"""
        with db.session() as session:
            return session.query(cls).all()

    def save(self) -> None:
        """保存记录（创建或更新）"""
        with db.session() as session:
            session.add(self)
            session.commit()

    def delete(self) -> None:
        """删除记录"""
        with db.session() as session:
            session.delete(self)
            session.commit()

    @classmethod
    def filter(cls, **kwargs) -> List[T]:
        """根据条件过滤记录"""
        with db.session() as session:
            query = session.query(cls)
            for key, value in kwargs.items():
                if not hasattr(cls, key):
                    raise ValueError(f"Invalid column name: {key}")
                if isinstance(value, (list, tuple)):
                    query = query.filter(getattr(cls, key).in_(value))
                else:
                    query = query.filter(getattr(cls, key) == value)
            return query.all()

    @classmethod
    def filter_one(cls, **kwargs) -> Optional[T]:
        """根据条件获取单条记录"""
        with db.session() as session:
            query = session.query(cls)
            for key, value in kwargs.items():
                if not hasattr(cls, key):
                    raise ValueError(f"Invalid column name: {key}")
                if isinstance(value, (list, tuple)):
                    query = query.filter(getattr(cls, key).in_(value))
                else:
                    query = query.filter(getattr(cls, key) == value)
            return query.first()

    @classmethod
    def filter_by(cls, **kwargs) -> List[T]:
        """根据条件模糊匹配记录"""
        with db.session() as session:
            query = session.query(cls)
            for key, value in kwargs.items():
                if not hasattr(cls, key):
                    raise ValueError(f"Invalid column name: {key}")
                query = query.filter(getattr(cls, key).like(f"%{value}%"))
            return query.all()

    @classmethod
    def count(cls, **kwargs) -> int:
        """统计符合条件的记录数"""
        with db.session() as session:
            query = session.query(cls)
            for key, value in kwargs.items():
                if not hasattr(cls, key):
                    raise ValueError(f"Invalid column name: {key}")
                if isinstance(value, (list, tuple)):
                    query = query.filter(getattr(cls, key).in_(value))
                else:
                    query = query.filter(getattr(cls, key) == value)
            return query.count()

    @classmethod
    def exists(cls, **kwargs) -> bool:
        """检查是否存在符合条件的记录"""
        return cls.count(**kwargs) > 0

    @classmethod
    def bulk_create(cls, objects: List[T]) -> None:
        """批量创建记录"""
        with db.session() as session:
            session.bulk_save_objects(objects)
            session.commit()

    @classmethod
    def bulk_update(cls, objects: List[T], update_fields: List[str]) -> None:
        """批量更新记录"""
        with db.session() as session:
            session.bulk_update_mappings(cls, [{
                'id': obj.id,
                **{field: getattr(obj, field) for field in update_fields}
            } for obj in objects])
            session.commit()

    @classmethod
    def bulk_delete(cls, ids: List[str]) -> None:
        """批量删除记录"""
        with db.session() as session:
            session.query(cls).filter(cls.id.in_([str(id) for id in ids])).delete(synchronize_session=False)
            session.commit()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }