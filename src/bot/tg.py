# telegram_bot.py - Telegram Bot Entry component for PaperDigestBot

"""
Module for handling Telegram bot interactions in the PaperDigestBot system.
This module implements the Telegram Bot functionality using the python-telegram-bot library.
It handles user interactions, communicates with the Dispatcher, and formats responses for Telegram.
"""

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, MessageReactionHandler
from loguru import logger
from pathlib import Path
import sys # Ensure sys is imported if REPO_DIR logic uses it
import os # Ensure os is imported
import asyncio # Added for database initialization
import atexit # Ensure atexit is imported

REPO_DIR = Path(__file__).resolve().parent.parent.parent
# add the src directory to the Python path
sys.path.append(str(REPO_DIR))

from src.dispatcher import *
from src.render import render_summary_tg
from src.models.message_record import MessageRecord
from src.models import BaseModel, UserSetting, ReactionRecord
from src.scheduler import start_scheduler, shutdown_scheduler # Removed add_user_schedule as it's not used directly here
from concurrent.futures import ProcessPoolExecutor

# Added for database initialization
from sqlalchemy import inspect, text
from src.db import db # Assuming db is the Database instance from src.db

global_pool = ProcessPoolExecutor(max_workers=4)
atexit.register(global_pool.shutdown)

async def run_in_global_pool(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(global_pool, func, *args)

# Load configuration from environment variables
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')

if not TELEGRAM_TOKEN and not os.getenv('TEST_MODE', 'false').lower() == 'true':
    logger.error("Telegram API token not found in environment. Please set TELEGRAM_BOT_TOKEN in .env file")
    raise ValueError("Telegram API token is required")

# Initialize the Telegram Application only if not in test mode
if os.getenv('TEST_MODE', 'false').lower() != 'true':
    application = Application.builder().token(TELEGRAM_TOKEN).build()
else:
    application = None  # Will be mocked in tests

# 设置自定义命令菜单
# from telegram import BotCommand # Already imported

async def set_bot_commands(bot):
    """设置 Telegram 机器人的自定义命令菜单"""
    commands = [
        BotCommand("start", "启动机器人"),
        BotCommand("recommend", "获取论文推荐"),
        # BotCommand("digest", "获取指定论文摘要"),
        # BotCommand("similar", "查找相似论文"),
        BotCommand("setting", "配置偏好"),
    ]
    await bot.set_my_commands(commands)
    logger.info("自定义命令菜单已设置")

# Handler for start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for the /start command.
    Sends a welcome message to the user with an introduction to the bot's functionality.
    """
    logger.info(f"User {update.effective_user.id} started the bot")
    welcome_message = (
        "欢迎使用 PaperDigestBot！\n\n"
        "我是您的论文推荐和摘要助手。以下是我的功能：\n"
        "- 使用 /recommend 获取论文推荐\n"
        # "- 使用 /digest 获取指定论文的摘要\n"
        # "- 使用 /similar 查找相似论文\n"
        "- 使用 /setting 配置您的偏好\n\n"
        "请随时发送 Arxiv ID 列表或使用上述命令与我互动！"
    )
    await update.message.reply_text(welcome_message)

def format_pat_safely(pat: str) -> str:
    """
    安全格式化PAT，只显示开头和结尾部分，中间用**替代

    Args:
        pat: GitHub Personal Access Token

    Returns:
        str: 格式化后的PAT字符串
    """
    if not pat:
        return "未设置"

    if len(pat) <= 8:
        # 如果PAT太短，只显示开头几位
        return pat[:2] + "**"

    # 显示开头4位和结尾4位，中间用**替代
    return pat[:8] + "**" + pat[-8:]

async def setting(update: Update, context: ContextTypes.DEFAULT_TYPE, initial=False):
    """
    处理设置命令，支持所有参数的配置
    支持格式：pat:您的令牌;repo:您的GitHub用户名/您的仓库名;cron:定时设置
    所有参数允许单独设置，同时设置多个参数需要使用分号隔开
    """
    logger.info(f"User {update.effective_user.id} accessed settings")
    settings_message = (
        "📝 *设置模板*\n\n"
        "完整设置：\n"
        "`pat:YOUR_PAT;repo:USER/REPO;cron:0 0 7 * * *`\n\n"
        "单独设置：\n"
        "`pat:YOUR_PAT`\n"
        "`repo:USER/REPO`\n"
        "`cron:0 0 7 * * *` (或 `cron:关闭` 来关闭定时任务)\n\n"
        "说明：\n"
        "• 必须是全英文符号, 最后一个参数不需要分号结尾\n"
        "• PAT：您的 GitHub 个人访问令牌\n"
        "• Repo：您的 GitHub 用户名和仓库名，格式为 USER/REPO\n"
        "• Cron：定时任务的 Cron 表达式 (5或6个字段), 或 '关闭' 来禁用"
    )
    if initial:
        settings_message = "首次设置：\n" + settings_message
    await update.message.reply_markdown(settings_message)

async def check_user_settings(user_id: str) -> tuple[bool, str]:
    """
    检查用户设置是否完整，包括必要的配置项

    Args:
        user_id: 用户ID

    Returns:
        tuple[bool, str]: (设置是否完整, 错误消息)
    """
    try:
        user_setting = UserSetting.get_by_id(user_id)
        if not user_setting:
            return False, "您还没有进行任何设置。请使用 /setting 命令进行配置。"

        if not user_setting.pat:
            return False, "您还没有设置 GitHub PAT。请使用 /setting 命令进行配置。"

        if not user_setting.github_id or not user_setting.repo_name:
            return False, "您还没有设置 GitHub 仓库信息。请使用 /setting 命令进行配置。"

        # Cron is optional, so no check for its absence unless it's malformed or a schedule is expected
        # If cron exists and is not '关闭', it should be a valid cron string.
        # This validation is primarily handled in parse_settings and when scheduling.
        return True, ""

    except Exception as e:
        logger.error(f"检查用户设置时出错: {e}")
        return False, "检查用户设置时出错，请稍后再试或联系管理员。"

def record_messages(send_results, update: Update, recommendations: pl.DataFrame):
    user_id = str(update.effective_user.id)
    group_id = str(update.effective_chat.id) if update.effective_chat.type in ['group', 'supergroup'] else None
    user_setting = UserSetting.get_by_id(user_id)
    if not user_setting:
        logger.error(f"User {user_id} settings not found")
        return

    logger.info(f"找到用户设置 - 仓库名: {user_setting.repo_name}")

    for result, arxiv_id in zip(send_results, recommendations['id']):
        try:
            record = MessageRecord.create(
                group_id=group_id,
                user_id=user_id,
                message_id=result,
                arxiv_id=arxiv_id,
                repo_name=user_setting.repo_name,
            )
            logger.info(f"消息记录创建成功 - ID: {record.id if hasattr(record, 'id') else 'unknown'}")
        except Exception as e:
            logger.error(f"记录消息时出错: {e} - 用户ID: {user_id}, Arxiv ID: {arxiv_id}")

async def process_recommendations_background(user_id: str, chat_id: int, message_id: int, context: ContextTypes.DEFAULT_TYPE):
    """
    后台处理推荐逻辑的异步任务
    """
    try:
        # 检查用户设置
        settings_ok, error_message = await check_user_settings(user_id)
        if not settings_ok:
            await context.bot.edit_message_text(
                text=error_message,
                chat_id=chat_id,
                message_id=message_id
            )
            return

        # Request recommendations from Dispatcher
        recommendations = await request_recommendations(user_id)
        if recommendations is None:
            await context.bot.edit_message_text(
                text="目前没有推荐的论文。稍后再试或调整您的偏好。",
                chat_id=chat_id,
                message_id=message_id
            )
            return
        else:
            await context.bot.edit_message_text(
                text="为您推荐的论文摘要如下：",
                chat_id=chat_id,
                message_id=message_id
            )

        # Format recommendations for Telegram
        formatted: dict[str, str] = await run_in_global_pool(render_summary_tg, recommendations)
        logger.debug(f"Formatted recommendations: {formatted}")

        tasks = [
            context.bot.send_message(chat_id=chat_id, text=rec, parse_mode='Markdown')
            for rec in formatted.values()
        ]
        send_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 简化 record_messages 调用
        user_setting = UserSetting.get_by_id(user_id)
        if user_setting:
            for result, arxiv_id in zip(send_results, recommendations['id']):
                try:
                    # Handle exceptions in send_results
                    if isinstance(result, Exception):
                        logger.error(f"发送消息时出错: {result}")
                        continue

                    # Debug: check what result contains
                    logger.debug(f"Result type: {type(result)}")
                    logger.debug(f"Result object: {result}")

                    # Extract message_id from the Message object
                    message_id = None
                    if hasattr(result, 'message_id'):
                        message_id = result.message_id
                        logger.info(f"成功提取 message_id: {message_id}")
                    else:
                        logger.error(f"Message对象没有message_id属性. 可用属性: {dir(result)}")
                        continue

                    if message_id is None:
                        logger.error(f"message_id为None，跳过记录")
                        continue

                    record = MessageRecord.create(
                        group_id=None,  # 私聊
                        user_id=user_id,
                        message_id=message_id,
                        arxiv_id=arxiv_id,
                        repo_name=user_setting.repo_name,
                    )
                    logger.info(f"消息记录创建成功 - ID: {record.id}")
                except Exception as e:
                    logger.error(f"记录消息时出错: {e}")
                    import traceback
                    logger.error(f"详细错误信息: {traceback.format_exc()}")

        logger.info(f"Sent {len(send_results)} recommendations to user {user_id}")

    except Exception as e:
        logger.error(f"Error in background recommendation processing: {e}")
        try:
            await context.bot.edit_message_text(
                text="抱歉，获取推荐时出错。请稍后再试。",
                chat_id=chat_id,
                message_id=message_id
            )
        except Exception as edit_error:
            logger.error(f"Failed to edit error message: {edit_error}")

# Handler for recommend command
async def recommend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for the /recommend command.
    Triggers the paper recommendation process and sends recommended paper abstracts to the user.
    """
    logger.info(f"User {update.effective_user.id} requested paper recommendations")
    initial_message = await update.message.reply_text("正在获取您的论文推荐，请稍候...")

    # 将处理逻辑提交到后台线程池
    asyncio.create_task(
        process_recommendations_background(
            user_id=str(update.effective_user.id),
            chat_id=update.effective_chat.id,
            message_id=initial_message.message_id,
            context=context
        )
    )

    logger.info(f"Recommendation request queued for user {update.effective_user.id}")
    # 立即返回，不等待后台任务完成
    return

async def display_current_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    显示当前用户设置
    """
    user_id = str(update.effective_user.id)
    try:
        user_setting = UserSetting.get_by_id(user_id)
        if not user_setting:
            settings_message = (
                "📋 *当前设置*\n\n"
                "您还没有进行任何设置。\n\n"
                "请使用以下格式进行设置：\n"
                "`/setting pat:YOUR_PAT;repo:USER/REPO;cron:0 0 7 * * *`\n\n"
            )
            await setting(update, context, initial=True)
            return

        # 格式化当前设置
        pat_display = format_pat_safely(user_setting.pat) if user_setting.pat else "未设置"
        repo_display = f"{user_setting.github_id}/{user_setting.repo_name}" if user_setting.github_id and user_setting.repo_name else "未设置"
        cron_display = user_setting.cron if user_setting.cron else "未设置"

        settings_message = (
            "📋 *当前设置*\n\n"
            f"• **PAT**: `{pat_display}`\n"
            f"• **仓库**: `{repo_display}`\n"
            f"• **定时任务**: `{cron_display}`\n\n"
            "如需修改设置，请使用：\n"
            "`/setting pat:YOUR_PAT;repo:USER/REPO;cron:0 0 7 * * *`\n\n"
            "单独修改某项设置：\n"
            "`/setting pat:YOUR_PAT`\n"
            "`/setting repo:USER/REPO`\n"
            "`/setting cron:0 0 7 * * *` (或 `cron:关闭`)"
        )

        await update.message.reply_markdown(settings_message)

    except Exception as e:
        logger.error(f"显示用户设置时出错: {e}")
        await update.message.reply_text("获取设置信息时出错，请稍后再试。")

async def update_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /setting command to update user settings.
    If no arguments are provided, it displays current settings.
    Otherwise, it passes the arguments to the dispatcher's update_settings function.
    """
    user_id = str(update.effective_user.id)
    if not context.args:
        # If /setting is called without arguments, show current settings
        await display_current_settings(update, context)
        return

    settings_text = " ".join(context.args)
    logger.info(f"User {user_id} attempting to update settings with: {settings_text}")

    # Call the dispatcher's update_settings function
    # This function is expected to return a tuple: (bool_success, str_message)
    success, message = await update_settings(user_id, settings_text)

    await update.message.reply_text(message)

async def handle_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理用户对消息的反应（点赞等表情）
    每个用户对同一消息只能有一个反应，新的反应会替换旧的反应

    Args:
        update: 更新对象
        context: 上下文对象
    """
    try:
        # 获取反应信息
        if not hasattr(update, 'message_reaction'):
            logger.warning("update 对象中没有 message_reaction 属性")
            return

        reaction = update.message_reaction
        if not reaction:
            logger.warning("message_reaction 为空")
            return

        user_id = str(update.effective_user.id)

        # 获取群组ID（如果在群组中）
        group_id = None
        if update.effective_chat and update.effective_chat.type in ['group', 'supergroup']:
            group_id = str(update.effective_chat.id)

        # 获取 emoji
        emoji = None
        is_removing = False

        # 检查是否是添加反应
        if hasattr(reaction, 'new_reaction') and reaction.new_reaction:
            for r in reaction.new_reaction:
                if hasattr(r, 'emoji'):
                    emoji = r.emoji
                    is_removing = False
                    break
        # 检查是否是移除反应
        elif hasattr(reaction, 'old_reaction') and reaction.old_reaction:
            for r in reaction.old_reaction:
                if hasattr(r, 'emoji'):
                    emoji = r.emoji
                    is_removing = True
                    break

        if not emoji:
            logger.warning("无法获取 emoji")
            return

        # 获取消息ID
        message_id = reaction.message_id if hasattr(reaction, 'message_id') else None

        if not message_id:
            logger.warning(f"无法获取消息ID")
            return

        logger.info(f"收到用户 {user_id} 对消息 {message_id} 的{'移除' if is_removing else '添加'}反应: {emoji}")

        # 获取消息记录 - 使用更精确的查找方法
        record = MessageRecord.get_by_context(group_id, user_id, message_id)
        if not record:
            logger.warning(f"未找到消息 {message_id} 的记录 (group_id: {group_id}, user_id: {user_id})")
            return

        # 记录反应
        try:
            # 检查用户是否已经对该消息有反应 - 使用上下文查找
            existing_reaction = ReactionRecord.get_by_context(group_id, user_id, message_id)

            if is_removing:
                # 如果是移除反应，删除记录
                if existing_reaction:
                    existing_reaction.delete()
                    logger.info(f"已删除用户 {user_id} 对论文 {record.arxiv_id} 的反应: {existing_reaction.emoji}")
            else:
                # 如果是添加反应
                if existing_reaction:
                    # 如果已有反应，更新为新的反应
                    old_emoji = existing_reaction.emoji
                    existing_reaction.emoji = emoji
                    existing_reaction.save()
                    logger.info(f"已更新用户 {user_id} 对论文 {record.arxiv_id} 的反应: {old_emoji} -> {emoji}")
                else:
                    # 如果没有反应，创建新的反应记录
                    reaction_record = ReactionRecord.create(
                        group_id=group_id,
                        user_id=user_id,
                        message_id=message_id,
                        arxiv_id=record.arxiv_id,
                        emoji=emoji
                    )
                    logger.info(f"已记录用户 {user_id} 对论文 {record.arxiv_id} 的反应: {emoji}")

        except Exception as e:
            logger.error(f"记录反应时出错: {str(e)}")
            import traceback
            logger.error(f"堆栈跟踪: {traceback.format_exc()}")

    except Exception as e:
        logger.error(f"处理反应时出错: {str(e)}")
        import traceback
        logger.error(f"堆栈跟踪: {traceback.format_exc()}")


# # Handler for digest command
# async def digest(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """
#     Handler for the /digest command.
#     Processes a list of Arxiv IDs provided by the user to fetch paper abstracts.
#     """
#     logger.info(f"User {update.effective_user.id} requested paper digests")
#     await update.message.reply_text("请提供 Arxiv ID 列表（每行一个），我将为您获取摘要。")
#     # The actual processing will happen in handle_message if the user sends IDs

# # Handler for similar command
# async def similar(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """
#     Handler for the /similar command.
#     Searches for similar papers based on a list of Arxiv IDs provided by the user.
#     """
#     logger.info(f"User {update.effective_user.id} requested similar papers")
#     await update.message.reply_text("请提供 Arxiv ID 列表（每行一个），我将为您查找相似论文。")
#     # The actual processing will happen in handle_message if the user sends IDs

# Run method
async def run():
    """
    Entry point to run the Telegram bot.
    Sets up command and message handlers, then starts the bot with polling.
    Uses a file lock to ensure only one instance is running.
    """
    # Database initialization is now handled synchronously in __main__ before this async run function is called.
    # No need to call check_and_initialize_db() here anymore.

    import fcntl
    # import sys # sys is already imported at the top

    logger.info("Starting Telegram Bot...")

    # 确保broker启动前已设置详细日志
    logger.debug("Broker startup")
    logger.debug("Broker startup complete")

    await application.initialize()
    logger.debug("Application initialized")
    await application.start()
    logger.debug("Application started")

    # Start the scheduler
    try:
        start_scheduler(application)
        logger.info("Scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        # Continue without scheduler - manual recommendations will still work

    # 然后测试实际的任务
    logger.debug("尝试提交正式 upsert_pat 任务...")
    a = await upsert_pat("test_user", "test_token")


    # Create a lock file to prevent multiple instances
    lock_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bot.lock')
    lock_file = open(lock_file_path, 'w')
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        logger.error("Another instance of the bot is already running. Exiting.")
        sys.exit(1)

    # Add command handlers
    # 添加正确且合适的handlers，包括reaction
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setting", update_settings_command)) # Changed to update_settings_command
    application.add_handler(CommandHandler("recommend", recommend))
    # application.add_handler(CommandHandler("digest", digest)) # digest command is commented out
    # application.add_handler(CommandHandler("similar", similar)) # similar command is commented out
    # handel reactions
    application.add_handler(MessageReactionHandler(handle_reaction))
    # Start the bot with polling
    logger.info("Bot started polling for updates")
    # 设置自定义命令菜单
    await set_bot_commands(application.bot)

    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    try:
        while True:
            await asyncio.sleep(1)  # 每小时检查一次，保持循环运行
    except KeyboardInterrupt:
        logger.info("Shutting down bot...")
        # Shutdown scheduler first
        try:
            shutdown_scheduler()
            logger.info("Scheduler shutdown completed")
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {e}")

        # 优雅地停止 bot
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        fcntl.lockf(lock_file, fcntl.LOCK_UN)
        lock_file.close()
        os.remove(lock_file_path)
        logger.info("Bot stopped.")

if __name__ == "__main__":
    """
    Main execution block.
    Runs the Telegram bot if this script is executed directly.
    """
    db.initialize() # This sets up db.engine

    asyncio.run(run())