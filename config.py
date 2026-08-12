"""
全局配置:模型名称、API地址、各Agent默认temperature、数据库路径、评分权重与阈值等。
"""
import os

MODEL_NAME = os.environ.get("QWEN_MODEL_NAME", "qwen-plus")
VISION_MODEL_NAME = os.environ.get("QWEN_VISION_MODEL_NAME", "qwen-vl-plus")
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

DB_PATH = os.environ.get("XHS_AGENT_DB_PATH", "database/xhs_agent.db")

# 各Agent推荐的temperature
# 筛选/拆解类需要稳定一致,温度低;选题/文案类需要创意多样性,温度高
TEMPERATURE_CONFIG = {
    # 原有 Agent
    "collector": 0.15,
    "filter": 0.25,
    "analyzer": 0.35,
    "topic_generator": 0.7,
    "copywriter": 0.8,
    # 新增 Agent
    "note_scorer": 0.25,
    "account_analyzer": 0.35,
    "trend_summarizer": 0.30,
    "title_generator": 0.70,
    "title_scorer": 0.25,
    "hashtag_recommender": 0.40,
    "image_extractor": 0,     # 图片提取需要稳定性
}

# ── 原有配置 ──
DEFAULT_TOP_N = 15
DEFAULT_TOPIC_COUNT = 10
DEFAULT_FORMAT_RATIO = {"视频笔记": 0.8, "图文笔记": 0.2}

# 热点筛选total_score(满分50)低于此阈值时,触发batch_warning
LOW_SCORE_THRESHOLD = 25

# ── 笔记爆款分析配置 ──
NOTE_SCORE_WEIGHTS = {
    "title_attractiveness": 0.20,   # 标题吸引力
    "cover_appeal": 0.15,           # 封面设计
    "copy_quality": 0.20,           # 文案质量
    "hashtag_strategy": 0.10,       # 标签策略
    "structure_flow": 0.15,         # 内容结构
    "emotion_hook": 0.10,           # 情绪触发
    "interaction_design": 0.10,     # 互动引导
}

# 等级阈值(50分制),score >= 阈值即为该等级
GRADE_THRESHOLDS = [
    (45, "S"),
    (40, "A"),
    (35, "B"),
    (25, "C"),
    (0,  "D"),
]

# ── 标题评分配置 ──
TITLE_VERDICT_THRESHOLDS = [
    (80, "推荐"),
    (60, "可用"),
    (0,  "不推荐"),
]

# ── Token预算管理 ──
MAX_ACCOUNT_NOTES_FOR_LLM = 15   # 竞品账号分析发送给LLM的最大笔记数
MAX_TREND_NOTES_FOR_LLM = 30     # 趋势分析发送给LLM的最大笔记数
