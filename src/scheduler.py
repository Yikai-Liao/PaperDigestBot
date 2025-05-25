"""
TODO: 适配信的基于cron的定时任务调度器
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from datetime import datetime
import pytz
from loguru import logger
from src.models import UserSetting
from src.dispatcher import request_recommendations
from sqlalchemy import event
from sqlalchemy.orm import Session

# 创建调度器实例
scheduler = AsyncIOScheduler(
    jobstores={
        'default': MemoryJobStore()
    },
    executors={
        'default': ThreadPoolExecutor(20)
    },
    timezone=pytz.UTC
)

def sync_user_schedule(user_id: str) -> bool:
    """
    同步用户的定时任务设置，现在基于 cron (UTC)
    
    Args:
        user_id: 用户ID
        
    Returns:
        bool: 是否成功同步
    """
    try:
        user_setting = UserSetting.get_by_id(user_id)
        if not user_setting:
            remove_user_schedule(user_id)
            logger.info(f"用户 {user_id} 设置不存在，已移除其定时任务（如果存在）。")
            return True
            
        # 检查是否有 cron 设置
        if not user_setting.cron:
            remove_user_schedule(user_id)
            logger.info(f"用户 {user_id} 未设置 cron，已移除其定时任务（如果存在）。")
            return True
            
        # 更新定时任务
        return add_user_schedule(user_id, user_setting.cron)
        
    except Exception as e:
        logger.error(f"同步用户 {user_id} 的定时任务失败: {e}")
        return False

def add_user_schedule(user_id: str, cron_expression: str) -> bool:
    """
    为用户添加基于 Cron (UTC) 的定时推荐任务
    
    Args:
        user_id: 用户ID
        cron_expression: Cron 表达式字符串 (应为 UTC 时间)
        
    Returns:
        bool: 是否成功添加任务
    """
    try:
        # 如果 cron_expression 为 None 或 '关闭'
        if not cron_expression or cron_expression.lower() == '关闭':
            remove_user_schedule(user_id)
            logger.info(f"用户 {user_id} 的 Cron 表达式为空或关闭，已移除其定时任务。")
            return True
            
        remove_user_schedule(user_id) # Remove existing before adding new
        
        job_id = f"recommend_{user_id}"
        scheduler.add_job(
            func=request_recommendations, 
            trigger=CronTrigger.from_string(cron_expression), # Uses scheduler's default UTC timezone
            args=[user_id],
            id=job_id,
            replace_existing=True
        )
        
        logger.info(f"已为用户 {user_id} 添加/更新定时推荐任务，Cron (UTC): '{cron_expression}'")
        return True
        
    except ValueError as e: # Catches errors from CronTrigger.from_string for bad cron expressions
        logger.error(f"添加定时任务失败: 无效的 Cron 表达式 '{cron_expression}' for user {user_id}. Error: {e}")
        remove_user_schedule(user_id) # Clean up if cron was bad
        return False
    except Exception as e:
        logger.error(f"添加定时任务失败 for user {user_id}: {e}")
        return False

def remove_user_schedule(user_id: str) -> bool:
    """
    移除用户的定时推荐任务
    
    Args:
        user_id: 用户ID
        
    Returns:
        bool: 是否成功移除任务
    """
    try:
        job_id = f"recommend_{user_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            logger.info(f"已移除用户 {user_id} 的定时推荐任务")
        return True
    except Exception as e:
        logger.error(f"移除定时任务失败: {e}")
        return False

def start_scheduler():
    """启动调度器"""
    if not scheduler.running:
        scheduler.start()
        logger.info("调度器已启动")
        
        # 注册数据库事件监听器
        @event.listens_for(Session, 'after_commit')
        def sync_schedules(session):
            """在数据库提交后同步定时任务"""
            try:
                # 获取所有修改过的 UserSetting 对象
                for obj in session.dirty:
                    if isinstance(obj, UserSetting):
                        logger.debug(f"Detected change in UserSetting for user {obj.id}, syncing schedule.")
                        sync_user_schedule(obj.id)
                # 获取所有新添加的 UserSetting 对象
                for obj in session.new:
                    if isinstance(obj, UserSetting):
                        logger.debug(f"Detected new UserSetting for user {obj.id}, syncing schedule.")
                        sync_user_schedule(obj.id)
                # 获取所有被删除的 UserSetting 对象
                for obj in session.deleted:
                    if isinstance(obj, UserSetting):
                        logger.debug(f"Detected deleted UserSetting for user {obj.id}, removing schedule.")
                        remove_user_schedule(obj.id)
            except Exception as e:
                logger.error(f"数据库事件触发的定时任务同步失败: {e}")

def shutdown_scheduler():
    """关闭调度器"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("调度器已关闭")