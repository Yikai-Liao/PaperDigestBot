# telegram_bot.py - Telegram Bot Entry component for PaperDigestBot

"""
Module for handling Telegram bot interactions in the PaperDigestBot system.
This module implements the Telegram Bot functionality using the python-telegram-bot library.
It handles user interactions, communicates with the Dispatcher, and formats responses for Telegram.
"""

import os
import sys
import toml
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from loguru import logger
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent.parent
# add the src directory to the Python path
sys.path.append(str(REPO_DIR))

from src.dispatcher import *
from src.render import render_summary_tg
from concurrent.futures import ProcessPoolExecutor
import atexit

global_pool = ProcessPoolExecutor(max_workers=4)
atexit.register(global_pool.shutdown)

async def run_in_global_pool(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(global_pool, func, *args)

# Load configuration from config.toml
config_path = os.getenv('CONFIG_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'config', 'config.toml'))
config = toml.load(config_path)
TELEGRAM_TOKEN = config.get('telegram', {}).get('token', '')

if not TELEGRAM_TOKEN and not os.getenv('TEST_MODE', 'false').lower() == 'true':
    logger.error("Telegram API token not found in configuration. Please set it in config/config.toml")
    raise ValueError("Telegram API token is required")

# Initialize the Telegram Application only if not in test mode
if os.getenv('TEST_MODE', 'false').lower() != 'true':
    application = Application.builder().token(TELEGRAM_TOKEN).build()
else:
    application = None  # Will be mocked in tests
    
# 设置自定义命令菜单
from telegram import BotCommand

async def set_bot_commands(bot):
    """设置 Telegram 机器人的自定义命令菜单"""
    commands = [
        BotCommand("start", "启动机器人"),
        BotCommand("recommend", "获取论文推荐"),
        BotCommand("digest", "获取指定论文摘要"),
        BotCommand("similar", "查找相似论文"),
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
        "- 使用 /digest 获取指定论文的摘要\n"
        "- 使用 /similar 查找相似论文\n"
        "- 使用 /setting 配置您的偏好\n\n"
        "请随时发送 Arxiv ID 列表或使用上述命令与我互动！"
    )
    await update.message.reply_text(welcome_message)
    # Optionally send initial settings or preferences prompt
    await setting(update, context, initial=True)

# Handler for setting command
async def setting(update: Update, context: ContextTypes.DEFAULT_TYPE, initial=False):
    """
    Handler for the /setting command or initial settings prompt.
    Allows users to configure bot settings such as notification frequency and recommendation preferences.
    """
    logger.info(f"User {update.effective_user.id} accessed settings")
    settings_message = (
        "您可以配置以下设置：\n"
        "1. 通知频率：每日、每周、关闭\n"
        "2. 推荐偏好：领域（如 AI, ML, Physics 等）\n"
        "3. GitHub PAT：设置您的个人访问令牌\n\n"
        "请回复类似 '频率:每日;领域:AI,ML' 的消息来更新您的设置。\n"
        "要设置 GitHub PAT，请发送 'pat:您的令牌' 消消息。"
    )
    if initial:
        settings_message = "首次设置：\n" + settings_message
    await update.message.reply_text(settings_message)

# Handler for recommend command
async def recommend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for the /recommend command.
    Triggers the paper recommendation process and sends recommended paper abstracts to the user.
    """
    logger.info(f"User {update.effective_user.id} requested paper recommendations")
    initial_message = await update.message.reply_text("正在获取您的论文推荐，请稍候...")
    
    try:
        # Request recommendations from Dispatcher
        recommendations = await request_recommendations(update.effective_user.id)
        # recommendations = pl.read_parquet("/tmp/paperdigest_ikd74_xi/summarized.parquet")
        if recommendations is None:
            await context.bot.edit_message_text(
                text="目前没有推荐的论文。稍后再试或调整您的偏好。",
                chat_id=update.effective_chat.id,
                message_id=initial_message.message_id
            )
            return
        else:
            await context.bot.edit_message_text(
                text="为您推荐的论文摘要如下：",
                chat_id=update.effective_chat.id,
                message_id=initial_message.message_id
            )
            
        # Format recommendations for Telegram
        recommendations: dict[str, str] = await run_in_global_pool(render_summary_tg, recommendations)
        logger.debug(f"Formatted recommendations: {recommendations}")
        tasks = [
            update.message.reply_text(rec, parse_mode='Markdown')
            for rec in recommendations.values()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)  # 并发执行并捕获异常
    except Exception as e:
        logger.error(f"Error fetching recommendations: {e}")
        await update.message.reply_text("抱歉，获取推荐时出错。请稍后再试。")

# Handler for digest command
async def digest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for the /digest command.
    Processes a list of Arxiv IDs provided by the user to fetch paper abstracts.
    """
    logger.info(f"User {update.effective_user.id} requested paper digests")
    await update.message.reply_text("请提供 Arxiv ID 列表（每行一个），我将为您获取摘要。")
    # The actual processing will happen in handle_message if the user sends IDs

# Handler for similar command
async def similar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for the /similar command.
    Searches for similar papers based on a list of Arxiv IDs provided by the user.
    """
    logger.info(f"User {update.effective_user.id} requested similar papers")
    await update.message.reply_text("请提供 Arxiv ID 列表（每行一个），我将为您查找相似论文。")
    # The actual processing will happen in handle_message if the user sends IDs

# Handler for messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for incoming messages.
    Processes non-command messages which could be Arxiv ID lists or feedback on papers.
    """
    user_text = update.message.text.strip()
    logger.info(f"Received message from user {update.effective_user.id}: {user_text[:50]}...")
    
    if not user_text:
        await update.message.reply_text("抱歉，我无法理解空消息。请提供有效的 Arxiv ID 列表或使用命令。")
        return
        
    try:
        # Check if the message contains Arxiv IDs (basic check for now)
        if "arxiv" in user_text.lower() or any(line.strip().isdigit() for line in user_text.split('\n')):
            # Assume it's a list of Arxiv IDs
            await update.message.reply_text("正在处理您的 Arxiv ID 列表，请稍候...")
            response = await process_arxiv_ids(update.effective_user.id, user_text)
            formatted_response = markdown_to_telegram(response)
            await update.message.reply_text(formatted_response, parse_mode='Markdown')
        elif "频率" in user_text or "领域" in user_text:
            # Assume it's a settings update
            await update.message.reply_text("正在更新您的设置...")
            response = await update_settings(update.effective_user.id, user_text)
            await update.message.reply_text(response)
        elif user_text.lower().startswith("pat:"):
            # Handle PAT token setting            
            pat_token = user_text.split(":", 1)[1].strip()
            if pat_token:  # Check if token is not empty
                await update.message.reply_text("正在设置您的 GitHub PAT...")
                try:
                    user_id = str(update.effective_user.id)
                    await upsert_pat(user_id, pat_token)
                    await update.message.reply_text("您的 GitHub PAT 已成功设置！")
                except Exception as e:
                    logger.error(f"Error setting PAT: {e}")
                    await update.message.reply_text("设置 PAT 时出错，请稍后再试。")
            else:
                await update.message.reply_text("无效的 PAT 令牌。请确保您复制了完整的令牌，格式应为 'pat:您的令牌'。")
        else:
            # Generic response for unrecognized input
            await update.message.reply_text("抱歉，我无法理解您的请求。请提供 Arxiv ID 列表或使用 /recommend, /digest, /similar 命令。")
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text("抱歉，处理您的请求时出错。请稍后再试。")

# Handler for reactions
async def handle_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for user reactions to messages.
    Records user feedback through reactions like thumbs up or thumbs down.
    """
    reaction = update.message_reaction
    logger.info(f"Received reaction from user {update.effective_user.id}: {reaction.emoji}")
    
    try:
        # Record the reaction with associated message ID and user ID
        await record_reaction(
            update.effective_user.id,
            update.message.message_id,
            reaction.emoji
        )
    except Exception as e:
        logger.error(f"Error recording reaction: {e}")

# Run method
async def run():
    """
    Entry point to run the Telegram bot.
    Sets up command and message handlers, then starts the bot with polling.
    Uses a file lock to ensure only one instance is running.
    """
    import fcntl
    import sys
    
    logger.info("Starting Telegram Bot...")
    
    # 确保broker启动前已设置详细日志
    logger.debug("Broker startup")
    logger.debug("Broker startup complete")
    
    await application.initialize()
    logger.debug("Application initialized")
    await application.start()
    logger.debug("Application started")


                
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
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setting", setting))
    application.add_handler(CommandHandler("recommend", recommend))
    application.add_handler(CommandHandler("digest", digest))
    application.add_handler(CommandHandler("similar", similar))
    
    # Add message handler for non-command messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add reaction handler (Note: This might require a different approach as python-telegram-bot v20 doesn't directly support reactions yet)
    # For now, we'll assume a placeholder; actual implementation may vary based on library updates
    # application.add_handler(MessageReactionHandler(handle_reaction))
    
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
    asyncio.run(run())