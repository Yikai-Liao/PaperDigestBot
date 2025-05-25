CREATE TABLE IF NOT EXISTS user_setting (
    id CHAR(32) PRIMARY KEY,
    github_id TEXT,
    pat TEXT,
    repo_name TEXT,
    cron TEXT,  -- 用于存储 Cron 表达式
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 添加字段注释
COMMENT ON TABLE user_setting IS '用户设置表：存储 Telegram 用户/群 的 GitHub 配置及定时任务cron表达式';
COMMENT ON COLUMN user_setting.id IS 'Telegram 用户 ID 或群组 ID，存为字符串格式';
COMMENT ON COLUMN user_setting.github_id IS 'GitHub 用户名，用于绑定 GitHub 账户';
COMMENT ON COLUMN user_setting.pat IS 'GitHub 访问令牌（Personal Access Token），用于访问 GitHub API';
COMMENT ON COLUMN user_setting.repo_name IS 'GitHub 仓库名，格式通常为 USER/REPO';
COMMENT ON COLUMN user_setting.cron IS 'Cron 表达式 (UTC)，用于安排定时任务';
COMMENT ON COLUMN user_setting.created_at IS '记录创建时间 (UTC)';
COMMENT ON COLUMN user_setting.updated_at IS '记录更新时间 (UTC)';

-- message_record table (ensure this is also up-to-date if changed, otherwise keep as is)
CREATE TABLE IF NOT EXISTS message_record (
    group_id CHAR(32),
    user_id CHAR(32),
    message_id BIGINT,
    arxiv_id TEXT,
    repo_name TEXT
);

COMMENT ON TABLE message_record IS '消息记录表：记录某群组或用户对某篇论文与对应仓库的消息行为';
COMMENT ON COLUMN message_record.group_id IS 'Telegram 群组 ID，支持负号，使用 CHAR 类型存储字符串形式';
COMMENT ON COLUMN message_record.user_id IS 'Telegram 用户 ID，使用 CHAR 类型存储';
COMMENT ON COLUMN message_record.message_id IS 'Telegram 消息 ID，对应一次消息记录';
COMMENT ON COLUMN message_record.arxiv_id IS 'arXiv 论文唯一编号，例如 2305.12345';
COMMENT ON COLUMN message_record.repo_name IS 'GitHub 仓库名，格式为 username/repo';