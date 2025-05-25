# dispatcher.py - Dispatcher component for PaperDigestBot

"""
Module for handling task dispatching and scheduling in the PaperDigestBot system.
This module uses taskiq with AioPika and Redis for task queuing and result storage.
"""
from loguru import logger
from src.action import run_workflow
import polars as pl # Assuming polars is used elsewhere or intended for request_recommendations
import os # Assuming os is used elsewhere or intended for request_recommendations
from typing import Optional, Dict, Any
from src.models import UserSetting


def parse_settings(settings_text: str) -> Dict[str, Any]:
    """
    解析设置文本为结构化数据
    
    参数:
        settings_text (str): 设置文本，支持以下格式：
            - repo:USER/REPO;pat:YOUR_PAT;cron:0 0 7 * * *;timezone:Asia/Shanghai
            - 单独设置也支持，用分号隔开
            
    返回:
        Dict[str, Any]: 解析后的设置字典
    """
    settings = {}
    # 分割不同的设置项
    items = settings_text.split(';')
    
    for item in items:
        if not item.strip():
            continue
            
        try:
            key, value = item.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            
            if key == 'pat':
                if not value:
                    raise ValueError("PAT 不能为空")
                settings['pat'] = value
            elif key == 'repo':
                if not value:
                    raise ValueError("Repo 不能为空")
                if '/' not in value:
                    raise ValueError("Repo 格式必须为 USER/REPO")
                github_id, repo_name = value.split('/', 1)
                if not github_id.strip() or not repo_name.strip():
                    raise ValueError("USER 和 REPO 都不能为空")
                settings['github_id'] = github_id.strip()
                settings['repo_name'] = repo_name.strip()
            elif key == 'cron':
                if not value:
                    raise ValueError("Cron 表达式不能为空")
                parts = value.split()
                if not (5 <= len(parts) <= 6) and value.lower() != '关闭':
                    raise ValueError(f"无效的 Cron 表达式格式: {value}. 应有5或6个字段，或为 '关闭'。")
                settings['cron'] = value
            else:
                raise ValueError(f"未知的设置项: {key}. 支持的设置项: pat, repo, cron")
        except ValueError as e:
            logger.warning(f"设置项解析错误: {e}")
            raise
        except Exception as e:
            logger.warning(f"无法解析设置项: {item}, 错误: {e}")
            raise ValueError(f"无法解析设置项: {item}")
            
    return settings

# Task for handling paper recommendation requests
async def request_recommendations(user_id: str, paper_ids: Optional[list[str]] = None) -> Optional[pl.DataFrame]:
    """
    处理用户论文推荐请求的任务
    
    参数:
        user_id (str): 请求推荐的用户ID
        paper_ids (Optional[list[str]]): 可选的论文ID列表，如果提供则只返回这些ID的论文
        
    返回:
        Optional[pl.DataFrame]: 推荐结果，如果没有设置或出错则返回 None
    """
    try:
        # 检查用户设置
        user_setting = UserSetting.get_by_id(user_id)
        if not user_setting:
            logger.warning(f"用户 {user_id} 没有设置，无法获取推荐")
            return None
            
        # 检查用户是否设置了 PAT
        if not user_setting.pat:
            logger.warning(f"用户 {user_id} 没有设置 PAT，无法获取推荐")
            return None
            
        # 检查用户是否设置了仓库信息
        if not user_setting.github_id or not user_setting.repo_name:
            logger.warning(f"用户 {user_id} 没有设置仓库信息，无法获取推荐")
            return None
            
        # 使用用户的设置运行工作流
        PAT = user_setting.pat
        OWNER = user_setting.github_id  # 使用用户的 GitHub ID
        REPO = user_setting.repo_name   # 使用用户的仓库名
        WORKFLOW_FILE = "recommend.yml"  # 替换为工作流文件名
        BRANCH = "main"  # 替换为分支名称
        INPUTS = {}  # 可选：工作流输入参数
        ARTIFACT_NAME = "summarized"
        
        tmp_dir = await run_workflow(PAT, OWNER, REPO, WORKFLOW_FILE, BRANCH, INPUTS, ARTIFACT_NAME)
        try:
            return pl.read_parquet(os.path.join(tmp_dir, "summarized.parquet"))
        except Exception as e:
            logger.error(f"读取parquet文件失败: {e}")
            return None
    except Exception as e:
        logger.error(f"获取推荐时出错: {e}")
        return None

# Task for processing user-provided Arxiv IDs
async def process_arxiv_ids(user_id: str, arxiv_ids: str) -> str:
    """
    Task to process a list of Arxiv IDs provided by a user.
    Returns a default result without actual processing.
    
    Args:
        user_id (str): The user ID submitting Arxiv IDs
        arxiv_ids (str): String containing Arxiv IDs, possibly in multiple formats
        
    Returns:
        str: Default processing response in markdown format
    """
    # Parse the input to extract Arxiv IDs (simplified for this example)
    arxiv_id_list = [id.strip() for id in arxiv_ids.split() if id.strip()]
    
    # Generate default response with the IDs
    default_response = f"""
# 论文摘要结果

已处理 {len(arxiv_id_list)} 个Arxiv ID:

"""
    # Add a default response for each ID
    for i, arxiv_id in enumerate(arxiv_id_list[:3]):  # Limit to first 3 IDs
        default_response += f"""
## 论文 {i+1}: {arxiv_id}

**标题**: 示例论文标题 {i+1}
**作者**: 示例作者
**发布日期**: 2024-05-01

**摘要**: 这是一个示例论文摘要，实际处理时会返回真实论文的摘要内容。

"""
    
    if len(arxiv_id_list) > 3:
        default_response += f"\n... 以及其他 {len(arxiv_id_list) - 3} 篇论文的摘要 ..."
        
    return default_response

# Task for updating user settings
async def update_settings(user_id: str, settings_text: str) -> str:
    """
    更新用户设置，使用新的关键字 pat, repo, cron
    
    参数:
        user_id (str): 更新设置的用户ID
        settings_text (str): 包含设置指令的文本
        
    返回:
        str: 更新确认消息
    """
    try:
        # 解析设置文本
        settings = parse_settings(settings_text)
        
        if not settings:
            return "设置格式无效，请使用正确的格式，例如：repo:USER/REPO;pat:YOUR_PAT;cron:0 0 7 * * *"
            
        # 获取或创建用户设置 (pat is handled separately if needed by upsert_pat)
        user_setting = UserSetting.get_or_create(user_id)
        
        response_parts = []
        pat_to_update = settings.pop('pat', None) # Handle PAT separately
        
        if 'github_id' in settings and 'repo_name' in settings:
            # These are parsed together from 'repo' key
            if UserSetting.update_github_id(user_id, settings['github_id']) and \
               UserSetting.update_repo_name(user_id, settings['repo_name']):
                response_parts.append(f"仓库更新为: {settings['github_id']}/{settings['repo_name']}")
        
        if 'cron' in settings:
            # Assuming UserSetting model has an update_cron method
            cron_value_to_store = settings['cron'] if settings['cron'].lower() != '关闭' else None
            if UserSetting.update_cron(user_id, cron_value_to_store):
                if cron_value_to_store:
                    response_parts.append(f"定时任务 Cron 更新为: {settings['cron']}")
                else:
                    response_parts.append("定时任务已关闭。")

        # 更新 PAT（如果存在）
        if pat_to_update:
            if await upsert_pat(user_id, pat_to_update):
                response_parts.append("GitHub PAT 已更新")
            
        if not response_parts and not pat_to_update:
             return "没有成功更新任何设置，或提供的设置项无效/未更改。请检查格式：repo:USER/REPO;pat:YOUR_PAT;cron:0 0 7 * * *"
            
        # The scheduling logic (calling add_user_schedule) has been removed.
        # The scheduler will pick up changes from the database via SQLAlchemy event listeners.
            
        return "设置已更新:\\n" + "\\n".join(response_parts)
        
    except ValueError as e:
        return f"设置格式错误: {str(e)}"
    except Exception as e:
        logger.error(f"更新设置时出错: {e}")
        return "更新设置时出错，请检查格式是否正确或联系管理员。"


async def upsert_pat(user_id: str, pat: str) -> bool:
    """
    更新或插入用户的 PAT (Personal Access Token) 的任务
    
    参数:
        user_id (str): 要更新 PAT 的用户ID
        pat (str): 要存储的个人访问令牌
        
    返回:
        bool: 操作是否成功
    """
    try:
        # 更新数据库中的 PAT
        user_setting = UserSetting.get_by_id(user_id)
        if user_setting:
            UserSetting.update_pat(user_id, pat)
        else:
            # 创建新用户设置
            user_setting = UserSetting(id=user_id, pat=pat)
            user_setting.save()
        
        logger.debug(f"PAT [{pat[:4]}...] for user {user_id} has been upserted.")
        return True
    except Exception as e:
        logger.error(f"更新 PAT 时出错: {e}")
        return False