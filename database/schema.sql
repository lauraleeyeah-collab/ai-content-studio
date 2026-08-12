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

-- ========== AI 超级自媒体工具（M1 图文工厂） ==========

-- 搜索词库：选题 → 搜索词分析 的沉淀，供标题关键词检查复用
CREATE TABLE IF NOT EXISTS search_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track TEXT,
    keyword TEXT,
    channel TEXT DEFAULT '小红书',
    search_intent TEXT,
    priority INTEGER DEFAULT 5,
    source_topic TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 内容资产：选题/图文/脚本/封面提示词 的统一入口（数据反哺的基础）
CREATE TABLE IF NOT EXISTS content_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_type TEXT,
    channel TEXT,
    title TEXT,
    content TEXT,
    search_keywords TEXT,
    persona_name TEXT,
    platform_review TEXT,
    status TEXT DEFAULT 'idea',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ========== AI 超级自媒体工具（M3 渠道中心） ==========

-- 6 平台规则库：算法权重/内容偏好/红线/AI标注要求/最佳实践（可编辑、可迭代）
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    algorithm_weights TEXT,
    content_prefs TEXT,
    red_lines TEXT,
    ai_label_required INTEGER DEFAULT 1,
    best_practices TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 多平台改写版本：同一素材按平台规则产出的版本 + 改写理由 + 合规结果
CREATE TABLE IF NOT EXISTS channel_rewrites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_asset_id INTEGER,
    target_channel TEXT,
    rewritten_content TEXT,
    rewrite_reasons TEXT,
    compliance_result TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 发布记录：发布清单的落库，支持数据回填（M4 数据中心）
CREATE TABLE IF NOT EXISTS publish_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER,
    channel TEXT,
    final_title TEXT,
    final_content TEXT,
    checklist_json TEXT,
    publish_time TEXT,
    status TEXT DEFAULT 'draft',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ========== AI 超级自媒体工具（M4 数据中心） ==========

-- 平台数据回填：发布后手动/CSV 导入的各渠道表现数据
CREATE TABLE IF NOT EXISTS platform_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    publish_record_id INTEGER,
    channel TEXT,
    content_title TEXT,
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    collects INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    play_rate REAL DEFAULT 0,
    completion_rate REAL DEFAULT 0,
    collected_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ========== AI 超级自媒体工具（P1 多账号/内容日历） ==========

-- 账号人设库：多账号档案，支持切换人设生成
CREATE TABLE IF NOT EXISTS personas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    domain TEXT,
    tone TEXT,
    style_guide_ref TEXT,
    channels TEXT,
    persona_description TEXT,
    is_default INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 发布计划：内容日历的数据源（计划发布时间/平台/状态）
CREATE TABLE IF NOT EXISTS publish_schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER,
    channel TEXT,
    content_title TEXT,
    planned_date TEXT,
    planned_time TEXT,
    status TEXT DEFAULT 'planned',
    persona_name TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
