-- 小红书爆款选题工具 数据库schema
-- 选用SQLite:个人使用场景,部署到Streamlit Community Cloud时不需要额外数据库服务

CREATE TABLE IF NOT EXISTS trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track TEXT,
    title TEXT,
    body_text TEXT,
    hashtags TEXT,
    likes INTEGER,
    comments INTEGER,
    collects INTEGER,
    shares INTEGER,
    blogger_fans INTEGER,
    post_date TEXT,
    note_type TEXT,
    note_link TEXT,
    extraction_confidence TEXT,
    total_score REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 已生成/已使用的选题,主要用于Agent3的去重判断(history_topics)
CREATE TABLE IF NOT EXISTS selected_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track TEXT,
    topic_title TEXT,
    core_angle TEXT,
    content_format TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS generated_copy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER,
    content_format TEXT,
    copy_text TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (topic_id) REFERENCES selected_topics(id)
);

-- 风格特征说明的版本管理,对应style_samples/目录里的style_guide文档
CREATE TABLE IF NOT EXISTS style_corpus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT,
    content TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ========== 新增功能表 ==========

-- 笔记爆款分析历史
CREATE TABLE IF NOT EXISTS note_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track TEXT,
    note_title TEXT,
    note_type TEXT,
    scores_json TEXT,
    total_score REAL,
    grade TEXT,
    improvement_priorities TEXT,
    raw_input_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 竞品账号信息
CREATE TABLE IF NOT EXISTS competitor_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track TEXT,
    account_name TEXT,
    fans_count INTEGER,
    positioning TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 竞品账号笔记
CREATE TABLE IF NOT EXISTS account_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    title TEXT,
    body_text TEXT,
    hashtags TEXT,
    likes INTEGER,
    comments INTEGER,
    collects INTEGER,
    shares INTEGER,
    post_date TEXT,
    note_type TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES competitor_accounts(id) ON DELETE CASCADE
);

-- 账号分析结果
CREATE TABLE IF NOT EXISTS account_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    computed_stats_json TEXT,
    llm_analysis_json TEXT,
    notes_analyzed INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES competitor_accounts(id) ON DELETE CASCADE
);

-- 趋势分析快照
CREATE TABLE IF NOT EXISTS trend_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track TEXT,
    time_range TEXT,
    notes_count INTEGER,
    computed_stats_json TEXT,
    llm_summary_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 标题优化历史
CREATE TABLE IF NOT EXISTS title_optimizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track TEXT,
    original_title TEXT,
    topic_context TEXT,
    variants_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 标签推荐历史
CREATE TABLE IF NOT EXISTS hashtag_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track TEXT,
    note_title TEXT,
    note_type TEXT,
    recommendations_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
