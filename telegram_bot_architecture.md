# Telegram Bot 架构规划（最终版修订）

## 概述
Telegram Bot 是 PaperDigestBot 系统的主要用户界面，负责处理用户请求并提供论文推荐、摘要和相似论文搜索结果。Bot 使用 `python-telegram-bot` 库实现，并与 Dispatcher 组件通过 Taskiq 进行异步通信。

## 核心功能
1. **用户交互**：处理用户通过 Telegram 发送的请求和命令。
2. **论文推荐**：接收从 Dispatcher 发送的推荐论文摘要，并以 Telegram 兼容的格式发送给用户。
3. **用户指定论文列表摘要**：允许用户发送 Arxiv ID 列表，Bot 将请求转发给 Dispatcher 处理，并将结果返回给用户。
4. **相似论文搜索**：处理用户发送的 Arxiv ID 列表，请求 Dispatcher 搜索相似论文，并将结果返回给用户。
5. **用户反馈**：收集用户对论文的反馈（如点赞或点踩），并将反馈发送给 Dispatcher 存储到用户偏好数据中。
6. **Markdown 格式化**：将从 Dispatcher 接收的 Markdown 格式内容转换为 Telegram 兼容的格式，以便用户能够正确查看论文摘要和相关信息。
7. **用户 Reaction 记录**：记录用户对每条消息的 reaction（如点赞、点踩等），并将这些 reaction 数据发送给 Dispatcher 进行存储和分析，用于改进推荐算法。

## 函数定义
- **`start` 函数**（`/start` 命令）：
  - 作用：当用户首次与 Bot 交互或发送 `/start` 命令时，Bot 应发送欢迎消息，介绍 Bot 的功能，并可能提供一些初始指导或帮助信息。
  - 实现：发送欢迎消息，包含 Bot 的功能介绍和使用说明。
- **`setting` 函数**（`/setting` 命令）：
  - 作用：允许用户配置 Bot 的设置，例如通知频率、推荐偏好等。
  - 实现：提供设置菜单或提示用户输入设置参数，并将设置保存到用户数据中。
- **`recommend` 函数**（`/recommend` 命令）：
  - 作用：触发论文推荐流程，向用户发送推荐的论文摘要。
  - 实现：请求 Dispatcher 提供推荐论文，将接收到的 Markdown 内容转换为 Telegram 兼容格式，并发送给用户。
- **`digest` 函数**（`/digest` 命令）：
  - 作用：处理用户指定的 Arxiv ID 列表，获取论文摘要。
  - 实现：解析用户提供的 Arxiv ID 列表，请求 Dispatcher 处理，将接收到的 Markdown 内容转换为 Telegram 兼容格式，并将摘要结果返回给用户。
- **`similar` 函数**（`/similar` 命令）：
  - 作用：根据用户提供的 Arxiv ID 列表，搜索相似论文。
  - 实现：解析用户提供的 Arxiv ID 列表，请求 Dispatcher 搜索相似论文，将接收到的 Markdown 内容转换为 Telegram 兼容格式，并将结果返回给用户。
- **`handle_message` 函数**：
  - 作用：处理用户发送的非命令消息，可能是 Arxiv ID 列表或对论文的反馈。
  - 实现：解析用户消息内容，判断是请求论文摘要还是反馈，并将请求或反馈转发给 Dispatcher 处理，然后将结果或确认消息返回给用户。
- **`handle_reaction` 函数**：
  - 作用：处理用户对消息的 reaction，记录用户的反馈。
  - 实现：监听用户对消息的 reaction（如点赞、点踩），将 reaction 数据与消息内容关联，并发送给 Dispatcher 存储到用户偏好数据中。

## 配置和运行
1. **API 令牌处理**：
   - Bot 需要从安全存储（如环境变量或配置文件）中读取 Telegram API 令牌。
   - 令牌不应硬编码在代码中，应通过配置文件或环境变量（如 `config/config.toml`）进行管理。
2. **Bot 启动**：
   - 使用 `python-telegram-bot` 库的 `Application` 类初始化 Bot，并配置令牌。
   - 设置命令处理器（如 `/start`, `/setting`, `/recommend`, `/digest`, `/similar`）和消息处理器来处理用户输入。
   - 设置 reaction 处理器来监听和记录用户对消息的 reaction。
   - 使用 `run_polling` 方法启动 Bot，允许持续监听用户消息。
3. **与 Dispatcher 的通信**：
   - Bot 通过 Taskiq 与 Dispatcher 进行异步通信，发送用户请求并接收处理结果。
   - 需要确保 Bot 在启动时与 Dispatcher 建立连接，并在运行过程中保持通信。
4. **错误处理和日志**：
   - 实现错误处理机制，记录错误信息以便调试。
   - 使用 `loguru` 库记录 Bot 的运行日志，包括用户交互和与 Dispatcher 的通信。
5. **Markdown 转换工具**：
   - 实现或使用现有库将 Markdown 内容转换为 Telegram 支持的格式（如 HTML 或直接使用 Telegram 的 Markdown 解析模式）。
   - 确保转换后的内容能够正确显示论文标题、摘要、链接等关键信息。

## Mermaid 图表
```mermaid
graph TD
    A[Telegram Users] -->|发送请求| B[Telegram Bot Entry]
    A -->|发送 Reaction| B
    B -->|转发请求| C[Dispatcher]
    B -->|转发 Reaction 数据| C
    C -->|处理请求| D[AI Abstract]
    C -->|处理请求| E[Vector Database]
    D -->|返回结果| C
    E -->|返回结果| C
    C -->|返回结果| B
    B -->|格式化并发送响应| A
    C -->|存储数据| F[Cloudflare R2]
    F -->|每日同步| G[Huggingface PaperDigest]