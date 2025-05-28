"""
Dispatcher component for PaperDigestBot

Module for handling task dispatching and scheduling in the PaperDigestBot system.
Provides functions for parsing user settings, requesting recommendations, and managing user configurations.
"""

import os
from typing import Any

import polars as pl
from loguru import logger

from src.action import run_workflow
from src.models import UserSetting
from src.utils import REPO_DIR


class SettingsParser:
    """Settings parser for user configuration strings"""

    SUPPORTED_KEYS = {"pat", "repo", "cron", "timezone"}

    @staticmethod
    def parse_settings(settings_text: str) -> dict[str, Any]:
        """
        解析设置文本为结构化数据

        参数:
            settings_text: 设置文本，支持以下格式：
                - repo:USER/REPO;pat:YOUR_PAT;cron:0 0 7 * * *;timezone:Asia/Shanghai
                - 单独设置也支持，用分号隔开

        返回:
            解析后的设置字典

        异常:
            ValueError: 当设置格式无效时
        """
        settings: dict[str, Any] = {}
        items = settings_text.split(";")

        for item in items:
            if not item.strip():
                continue

            try:
                if ":" not in item:
                    raise ValueError(f"无法解析设置项: {item}")

                key, value = item.split(":", 1)
                key = key.strip().lower()
                value = value.strip()

                if key == "pat":
                    settings["pat"] = SettingsParser._validate_pat(value)
                elif key == "repo":
                    github_id, repo_name = SettingsParser._validate_repo(value)
                    settings.update({"github_id": github_id, "repo_name": repo_name})
                elif key == "cron":
                    settings["cron"] = SettingsParser._validate_cron(value)
                elif key == "timezone":
                    settings["timezone"] = SettingsParser._validate_timezone(value)
                else:
                    raise ValueError(
                        f"未知的设置项: {key}. 支持的设置项: {', '.join(SettingsParser.SUPPORTED_KEYS)}"
                    )

            except ValueError:
                raise
            except Exception as e:
                logger.warning(f"无法解析设置项: {item}, 错误: {e}")
                raise ValueError(f"无法解析设置项: {item}")

        return settings

    @staticmethod
    def _validate_pat(value: str) -> str:
        """Validate PAT value"""
        if not value:
            raise ValueError("PAT 不能为空")
        return value

    @staticmethod
    def _validate_repo(value: str) -> tuple[str, str]:
        """Validate and parse repository value"""
        if not value:
            raise ValueError("Repo 不能为空")
        if "/" not in value:
            raise ValueError("Repo 格式必须为 USER/REPO")

        github_id, repo_name = value.split("/", 1)
        if not github_id.strip() or not repo_name.strip():
            raise ValueError("USER 和 REPO 都不能为空")

        return github_id.strip(), repo_name.strip()

    @staticmethod
    def _validate_cron(value: str) -> str:
        """Validate cron expression"""
        if not value:
            raise ValueError("Cron 表达式不能为空")

        if value.lower() == "关闭":
            return value

        parts = value.split()
        if not (5 <= len(parts) <= 6):
            raise ValueError(f"无效的 Cron 表达式格式: {value}. 应有5或6个字段，或为 '关闭'。")

        return value

    @staticmethod
    def _validate_timezone(value: str) -> str:
        """Validate timezone value"""
        if not value:
            raise ValueError("时区不能为空")
        return value


def parse_settings(settings_text: str) -> dict[str, Any]:
    """
    Legacy function for backward compatibility
    """
    return SettingsParser.parse_settings(settings_text)


class RecommendationService:
    """Service for handling paper recommendation requests"""

    def __init__(self, workflow_file: str = "recommend.yml", branch: str = "main"):
        self.workflow_file = workflow_file
        self.branch = branch
        self.artifact_name = "summarized"

    async def request_recommendations(
        self, user_id: str, paper_ids: list[str] | None = None
    ) -> pl.DataFrame | None:
        """
        处理用户论文推荐请求的任务

        参数:
            user_id: 请求推荐的用户ID
            paper_ids: 可选的论文ID列表，如果提供则只返回这些ID的论文

        返回:
            推荐结果，如果没有设置或出错则返回 None
        """
        try:
            user_setting = self._get_user_setting(user_id)
            if not user_setting:
                return None

            if not self._validate_user_setting(user_setting, user_id):
                return None

            # For development/testing, return test data
            return self._get_test_data()

            # Production code (commented out for now)
            # return await self._run_workflow(user_setting, paper_ids)

        except Exception as e:
            logger.error(f"获取推荐时出错: {e}")
            return None

    def _get_user_setting(self, user_id: str) -> UserSetting | None:
        """Get user setting by ID"""
        user_setting = UserSetting.get_by_id(user_id)
        if not user_setting:
            logger.warning(f"用户 {user_id} 没有设置，无法获取推荐")
        return user_setting

    def _validate_user_setting(self, user_setting: UserSetting, user_id: str) -> bool:
        """Validate user setting has required fields"""
        if not user_setting.pat:
            logger.warning(f"用户 {user_id} 没有设置 PAT，无法获取推荐")
            return False

        if not user_setting.github_id or not user_setting.repo_name:
            logger.warning(f"用户 {user_id} 没有设置仓库信息，无法获取推荐")
            return False

        return True

    def _get_test_data(self) -> pl.DataFrame:
        """Get test data for development"""
        test_file = REPO_DIR / "tests" / "data" / "summarized.parquet"
        return pl.read_parquet(test_file)

    async def _run_workflow(
        self, user_setting: UserSetting, paper_ids: list[str] | None = None
    ) -> pl.DataFrame | None:
        """Run GitHub workflow and return results"""
        try:
            inputs = {"paper_ids": paper_ids} if paper_ids else {}
            tmp_dir = await run_workflow(
                pat=user_setting.pat,
                owner=user_setting.github_id,
                repo=user_setting.repo_name,
                workflow_file=self.workflow_file,
                branch=self.branch,
                inputs=inputs,
                artifact_name=self.artifact_name,
            )

            parquet_file = os.path.join(tmp_dir, "summarized.parquet")
            return pl.read_parquet(parquet_file)
        except Exception as e:
            logger.error(f"读取parquet文件失败: {e}")
            return None


# Legacy function for backward compatibility
async def request_recommendations(
    user_id: str, paper_ids: list[str] | None = None
) -> pl.DataFrame | None:
    """
    Legacy function for backward compatibility
    """
    service = RecommendationService()
    return await service.request_recommendations(user_id, paper_ids)


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
async def update_settings(user_id: str, settings_text: str) -> tuple[bool, str]:
    """
    更新用户设置，使用新的关键字 pat, repo, cron

    参数:
        user_id (str): 更新设置的用户ID
        settings_text (str): 包含设置指令的文本

    返回:
        tuple[bool, str]: (操作是否部分成功, 更新确认消息)
    """
    response_messages = []
    any_setting_applied_successfully = False
    try:
        parsed_settings = parse_settings(settings_text)  # Can raise ValueError

        if not parsed_settings:
            return (
                False,
                "设置格式无效或未提供有效设置项。请使用正确的格式，例如：repo:USER/REPO;pat:YOUR_PAT;cron:0 0 7 * * *",
            )

        # Ensure user_setting object exists for operations if needed by direct attribute access,
        # though current model methods (update_github_id, etc.) fetch their own.
        # UserSetting.get_or_create(user_id) # Original code had this, can be kept if other parts rely on it.

        pat_to_update = parsed_settings.get("pat")
        github_id_to_update = parsed_settings.get("github_id")
        repo_name_to_update = parsed_settings.get("repo_name")
        cron_to_update = parsed_settings.get("cron")

        # Handle repo (github_id and repo_name)
        if (
            github_id_to_update and repo_name_to_update
        ):  # Both must be present if 'repo' key was parsed
            try:
                UserSetting.create_or_update(
                    user_id, github_id=github_id_to_update, repo_name=repo_name_to_update
                )
                response_messages.append(f"仓库更新为: {github_id_to_update}/{repo_name_to_update}")
                any_setting_applied_successfully = True
            except Exception as e:
                logger.error(f"更新仓库信息时出错 for user {user_id}: {e}")
                response_messages.append(
                    f"仓库 ({github_id_to_update}/{repo_name_to_update}) 更新失败。"
                )
        elif github_id_to_update or repo_name_to_update:  # Only one part of repo provided
            response_messages.append(
                "仓库信息不完整，请同时提供 GitHub 用户名和仓库名 (例如: repo:USER/REPO)。"
            )

        # Handle cron
        if cron_to_update is not None:  # Check if 'cron' key was present in parsed_settings
            cron_value_to_store = cron_to_update if cron_to_update.lower() != "关闭" else None
            try:
                # Using create_or_update as UserSetting.update_cron classmethod doesn't exist
                UserSetting.create_or_update(user_id, cron=cron_value_to_store)

                # Update scheduler with new cron setting
                from src.scheduler import sync_user_schedule_from_settings

                if sync_user_schedule_from_settings(user_id):
                    if cron_value_to_store:
                        response_messages.append(f"定时任务 Cron 更新为: {cron_to_update}")
                    else:
                        response_messages.append("定时任务已关闭。")
                    any_setting_applied_successfully = True
                else:
                    response_messages.append("定时任务设置已保存，但调度器更新失败。")

            except Exception as e:
                logger.error(f"更新 Cron 时出错 for user {user_id}: {e}")
                response_messages.append("定时任务 Cron 更新失败。")

        # Handle PAT
        if pat_to_update:
            if await upsert_pat(user_id, pat_to_update):
                response_messages.append("GitHub PAT 已更新")
                any_setting_applied_successfully = True
            else:
                response_messages.append("GitHub PAT 更新失败。")

        if not response_messages:  # No settings were processed from the input string
            # This case might occur if parse_settings returned a dict with unknown keys
            # or keys that were not handled above (e.g. only 'timezone' if it's not handled yet)
            return (False, "未识别到有效设置项或提供的设置项无法处理。请检查格式。")

        final_message = "设置处理结果:\\n" + "\\n".join(response_messages)
        return (any_setting_applied_successfully, final_message)

    except ValueError as e:  # From parse_settings
        return (False, f"设置格式错误: {str(e)}")
    except Exception as e:
        logger.error(f"更新设置时出错 (用户: {user_id}): {e}")
        import traceback

        logger.error(traceback.format_exc())
        return (False, "更新设置时发生内部错误，请联系管理员。")


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
        # 使用 create_or_update 方法统一处理
        UserSetting.create_or_update(user_id, pat=pat)
        logger.debug(f"PAT [{pat[:4]}...] for user {user_id} has been upserted.")
        return True
    except Exception as e:
        logger.error(f"更新 PAT 时出错: {e}")
        return False
