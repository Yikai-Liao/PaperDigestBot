# telegram_bot.py - Telegram Bot Entry component for PaperDigestBot

"""
Module for handling Telegram bot interactions in the PaperDigestBot system.
This module implements the Telegram Bot functionality using the python-telegram-bot library.
It handles user interactions, communicates with the Dispatcher via Taskiq, and formats responses for Telegram.
"""

import os
import toml
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ChatMemberHandler
from loguru import logger

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

# Placeholder for Taskiq client to communicate with Dispatcher
# This will be initialized when Taskiq setup is complete
taskiq_client = None

def setup_taskiq_client(client):
    """Set up the Taskiq client for communication with Dispatcher."""
    global taskiq_client
    taskiq_client = client
    logger.info("Taskiq client setup completed for Telegram Bot")

# Markdown to Telegram format conversion utility
def markdown_to_telegram(md_text):
    """
    Convert Markdown text to a format compatible with Telegram.
    This is a basic implementation and can be enhanced based on specific formatting needs.
    """
    # Replace Markdown bold (**text**) with Telegram bold (*text*)
    formatted_text = md_text.replace('**', '*')
    # Replace Markdown italic (_text_) with Telegram italic (_text_)
    # Already compatible, no change needed for italic
    # Replace Markdown links ([text](url)) with Telegram links (text (url))
    import re
    formatted_text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', formatted_text)
    return formatted_text

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
        "2. 推荐偏好：领域（如 AI, ML, Physics 等）\n\n"
        "请回复类似 '频率:每日;领域:AI,ML' 的消息来更新您的设置。"
    )
    if initial:
        settings_message = "首次设置：" + settings_message
    await update.message.reply_text(settings_message)

# Handler for recommend command
async def recommend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for the /recommend command.
    Triggers the paper recommendation process and sends recommended paper abstracts to the user.
    """
    logger.info(f"User {update.effective_user.id} requested paper recommendations")
    await update.message.reply_text("正在获取您的论文推荐，请稍候...")
    
    if taskiq_client is None:
        logger.error("Taskiq client not initialized")
        await update.message.reply_text("抱歉，系统尚未完全初始化。请稍后再试。")
        return
    
    try:
        # Request recommendations from Dispatcher via Taskiq
        recommendations = await taskiq_client.request_recommendations(user_id=update.effective_user.id)
        if not recommendations:
            await update.message.reply_text("目前没有推荐的论文。稍后再试或调整您的偏好。")
            return
            
        # Format recommendations for Telegram
        formatted_recommendations = markdown_to_telegram(recommendations)
        await update.message.reply_text(formatted_recommendations, parse_mode='Markdown')
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
        
    if taskiq_client is None:
        logger.error("Taskiq client not initialized")
        await update.message.reply_text("抱歉，系统尚未完全初始化。请稍后再试。")
        return
    
    try:
        # Check if the message contains Arxiv IDs (basic check for now)
        if "arxiv" in user_text.lower() or any(line.strip().isdigit() for line in user_text.split('\n')):
            # Assume it's a list of Arxiv IDs
            await update.message.reply_text("正在处理您的 Arxiv ID 列表，请稍候...")
            response = await taskiq_client.process_arxiv_ids(user_id=update.effective_user.id, arxiv_ids=user_text)
            formatted_response = markdown_to_telegram(response)
            await update.message.reply_text(formatted_response, parse_mode='Markdown')
        elif "频率" in user_text or "领域" in user_text:
            # Assume it's a settings update
            await update.message.reply_text("正在更新您的设置...")
            response = await taskiq_client.update_settings(user_id=update.effective_user.id, settings_text=user_text)
            await update.message.reply_text(response)
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
    
    if taskiq_client is None:
        logger.error("Taskiq client not initialized")
        return
    
    try:
        # Record the reaction with associated message ID and user ID
        await taskiq_client.record_reaction(
            user_id=update.effective_user.id,
            message_id=update.message.message_id,
            reaction=reaction.emoji
        )
    except Exception as e:
        logger.error(f"Error recording reaction: {e}")

# Run method
def run():
    """
    Entry point to run the Telegram bot.
    Sets up command and message handlers, then starts the bot with polling.
    """
    logger.info("Starting Telegram Bot...")
    
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
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    """
    Main execution block.
    Runs the Telegram bot if this script is executed directly.
    """
    run()