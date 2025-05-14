# dispatcher.py - Dispatcher component for PaperDigestBot

"""
Module for handling task dispatching and scheduling in the PaperDigestBot system.
This module uses taskiq with AioPika and Redis for task queuing and result storage.
"""
import asyncio
import os
from src.pat import EncryptedTokenManagerDB
from src.config import Config
from loguru import logger
from src.action import run_workflow
import polars as pl
from typing import Optional


cfg = Config.default()

# Task for handling paper recommendation requests
async def request_recommendations(user_id: str) -> Optional[pl.DataFrame]:
    """
    Task to handle paper recommendations for users.
    Returns a default result without actual processing.
    
    Args:
        user_id (str): The user ID requesting recommendations
        
    Returns:
        str: Default recommendation response in markdown format
    """
    # Default response in markdown format
    PAT = ""  # 替换为你的 Personal Access Token
    OWNER = "Yikai-Liao"  # 替换为仓库所有者（用户名或组织名）
    REPO = "PaperDigestAction"  # 替换为仓库名称
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
    Task to update user settings based on provided text.
    Returns a default success message without actual processing.
    
    Args:
        user_id (str): The user ID updating settings
        settings_text (str): Text containing setting instructions
        
    Returns:
        str: Default confirmation message
    """
    return f"设置已更新: {settings_text}"

async def upsert_pat(user_id: str, pat: str) -> bool:
    """
    Task to upsert a PAT (Personal Access Token) for a user.
    
    Args:
        user_id (str): The user ID for which the PAT is being upserted
        pat (str): The Personal Access Token to be stored
    """
    # 路径已经在PATConfig中通过validator转换为绝对路径
    manager = EncryptedTokenManagerDB(db_path=cfg.pat.db_path, key=cfg.pat.key)
    
    # 将同步SQLite操作转换为异步操作
    await asyncio.to_thread(manager.add_token, user_id, pat)
    
    logger.debug(f"PAT [{pat[:4]}...] for user {user_id} has been upserted.")
    return True

# Task for recording user reactions to papers
async def record_reaction(user_id: str, message_id: int, reaction: str) -> None:
    """
    Task to record user reactions to papers.
    Logs the reaction without actual processing.
    
    Args:
        user_id (str): The user ID who reacted
        message_id (int): The ID of the message reacted to
        reaction (str): The reaction emoji
    """
    return None