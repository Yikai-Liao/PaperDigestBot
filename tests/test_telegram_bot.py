import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import asyncio
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes

# 导入要测试的模块
from bot.tg import start, setting, recommend, digest, similar, handle_message, handle_reaction, markdown_to_telegram

# 固定装置：模拟 Update 对象
@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 12345
    update.message = MagicMock(spec=Message)
    update.message.text = "test message"
    update.message.chat = MagicMock(spec=Chat)
    update.message.chat.id = 67890
    return update

# 固定装置：模拟 Context 对象
@pytest.fixture
def mock_context():
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    return context

# 测试 markdown_to_telegram 函数
def test_markdown_to_telegram():
    md_text = "This is **bold** and [link](http://example.com)"
    expected = "This is *bold* and link (http://example.com)"
    result = markdown_to_telegram(md_text)
    assert result == expected

# 测试 start 函数
@pytest.mark.asyncio
async def test_start(mock_update, mock_context):
    with patch.object(mock_update.message, 'reply_text', new=AsyncMock()) as mock_reply:
        await start(mock_update, mock_context)
        assert mock_reply.call_count == 3
        assert "欢迎使用 PaperDigestBot" in mock_reply.call_args_list[0][0][0]
        assert "首次设置" in mock_reply.call_args_list[1][0][0]

# 测试 setting 函数
@pytest.mark.asyncio
async def test_setting(mock_update, mock_context):
    with patch.object(mock_update.message, 'reply_text', new=AsyncMock()) as mock_reply:
        await setting(mock_update, mock_context)
        mock_reply.assert_called_once()
        assert "您可以配置以下设置" in mock_reply.call_args[0][0]

# 测试 recommend 函数 - 成功案例
@pytest.mark.asyncio
async def test_recommend_success(mock_update, mock_context):
    mock_client = MagicMock()
    mock_client.request_recommendations = AsyncMock(return_value="推荐的论文内容")
    with patch('bot.tg.taskiq_client', mock_client), \
         patch.object(mock_update.message, 'reply_text', new=AsyncMock()) as mock_reply:
        await recommend(mock_update, mock_context)
        mock_reply.assert_called()
        assert "正在获取您的论文推荐" in mock_reply.call_args_list[0][0][0]
        assert "推荐的论文内容" in mock_reply.call_args_list[1][0][0]

# 测试 recommend 函数 - 客户端未初始化
@pytest.mark.asyncio
async def test_recommend_not_initialized(mock_update, mock_context):
    with patch('bot.tg.taskiq_client', None), \
         patch.object(mock_update.message, 'reply_text', new=AsyncMock()) as mock_reply:
        await recommend(mock_update, mock_context)
        assert mock_reply.call_count == 2
        assert "正在获取您的论文推荐" in mock_reply.call_args_list[0][0][0]
        assert "系统尚未完全初始化" in mock_reply.call_args_list[1][0][0]

# 测试 digest 函数
@pytest.mark.asyncio
async def test_digest(mock_update, mock_context):
    with patch.object(mock_update.message, 'reply_text', new=AsyncMock()) as mock_reply:
        await digest(mock_update, mock_context)
        mock_reply.assert_called_once()
        assert "请提供 Arxiv ID 列表" in mock_reply.call_args[0][0]

# 测试 similar 函数
@pytest.mark.asyncio
async def test_similar(mock_update, mock_context):
    with patch.object(mock_update.message, 'reply_text', new=AsyncMock()) as mock_reply:
        await similar(mock_update, mock_context)
        mock_reply.assert_called_once()
        assert "请提供 Arxiv ID 列表" in mock_reply.call_args[0][0]

# 测试 handle_message 函数 - Arxiv ID 列表
@pytest.mark.asyncio
async def test_handle_message_arxiv_ids(mock_update, mock_context):
    mock_update.message.text = "arxiv:1234.5678"
    mock_client = MagicMock()
    mock_client.process_arxiv_ids = AsyncMock(return_value="处理后的摘要内容")
    with patch('bot.tg.taskiq_client', mock_client), \
         patch.object(mock_update.message, 'reply_text', new=AsyncMock()) as mock_reply:
        await handle_message(mock_update, mock_context)
        mock_reply.assert_called()
        assert "正在处理您的 Arxiv ID 列表" in mock_reply.call_args_list[0][0][0]
        assert "处理后的摘要内容" in mock_reply.call_args_list[1][0][0]

# 测试 handle_message 函数 - 设置更新
@pytest.mark.asyncio
async def test_handle_message_settings(mock_update, mock_context):
    mock_update.message.text = "频率:每日;领域:AI,ML"
    mock_client = MagicMock()
    mock_client.update_settings = AsyncMock(return_value="设置已更新")
    with patch('bot.tg.taskiq_client', mock_client), \
         patch.object(mock_update.message, 'reply_text', new=AsyncMock()) as mock_reply:
        await handle_message(mock_update, mock_context)
        mock_reply.assert_called()
        assert "正在更新您的设置" in mock_reply.call_args_list[0][0][0]
        assert "设置已更新" in mock_reply.call_args_list[1][0][0]

# 测试 handle_message 函数 - 无法理解的消息
@pytest.mark.asyncio
async def test_handle_message_unrecognized(mock_update, mock_context):
    mock_update.message.text = "无法理解的消息"
    with patch('bot.tg.taskiq_client', MagicMock()), \
         patch.object(mock_update.message, 'reply_text', new=AsyncMock()) as mock_reply:
        await handle_message(mock_update, mock_context)
        mock_reply.assert_called_once()
        assert "抱歉，我无法理解您的请求" in mock_reply.call_args[0][0]

# 测试 handle_reaction 函数
@pytest.mark.asyncio
async def test_handle_reaction(mock_update, mock_context):
    mock_update.message_reaction = MagicMock()
    mock_update.message_reaction.emoji = "👍"
    mock_update.message.message_id = 98765
    mock_client = MagicMock()
    mock_client.record_reaction = AsyncMock()
    with patch('bot.tg.taskiq_client', mock_client):
        await handle_reaction(mock_update, mock_context)
        mock_client.record_reaction.assert_called_once_with(
            user_id=12345,
            message_id=98765,
            reaction="👍"
        )