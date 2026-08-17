"""
6 平台规则库（M3 渠道中心核心资产）。

规则卡结构：
- algorithm_weights: 算法权重排序（调研报告 2026 口径）
- content_prefs: 内容偏好
- red_lines: 平台红线
- ai_label_required: 是否强制 AI 标注
- best_practices: 最佳实践（可直接指导改写）
- platform_spec: 平台工作台规格（封面/正文/标题/互动机制，供 platform_workshop 使用）
- collect_keywords: 收藏引导关键词（逗号分隔，供互动策略确定性检查）
- share_keywords: 分享引导关键词（逗号分隔）
- copy_min_words / copy_max_words: 正文字数合理区间（供 rule_checks 校验）

规则库外置存储，可随平台规则变化迭代（SQLite channels 表 + 本文件为默认种子）。
"""

CHANNEL_RULES = [
    {
        "name": "小红书",
        "algorithm_weights": "点击率 > 停留时长 > 收藏 > 评论/转发 > 点赞（CES 排序）",
        "content_prefs": "搜索流量占比超 55%，实用收藏价值 > 情绪价值 > 娱乐价值；中长视频（1-3分钟）扶持，长尾 90 天",
        "red_lines": "站外导流、极限词、刷量、搬运",
        "ai_label_required": 1,
        "best_practices": "标题前 20 字放长尾关键词；AI 创作强制标注；正文清单体/步骤体；结尾引导收藏",
        "platform_spec": (
            "封面：3:4 竖版 1080×1440，人物/产品居中偏右，顶部 1/3 留文字位，文字大且高对比；"
            "正文：清单体/步骤体 800-1500 字，搜索关键词前置，结尾显性收藏指令；"
            "标题：前 20 字放长尾关键词；互动机制：收藏、评论、转发、点赞（收藏权重最高）。"
        ),
        "collect_keywords": "收藏",
        "share_keywords": "转发,分享,发给",
        "copy_min_words": 150,
        "copy_max_words": 1000,
    },
    {
        "name": "抖音",
        "algorithm_weights": "收藏率 > 复访率 > 铁粉互动 > 5秒完播 > 完播率 > 点赞/评论 > 转发（2026 新规）",
        "content_prefs": "干货拉升收藏；真实案例；3秒钩子；显性「建议收藏」指令；7天长效赛马",
        "red_lines": "稀缺逼单、虚假价格、售后承诺、虚假权威",
        "ai_label_required": 1,
        "best_practices": "前 5 秒强钩子；结尾显性收藏指令；行动指令不能只靠暗示；评论区置顶引导收藏",
        "platform_spec": (
            "封面：9:16 竖版 1080×1920，前 3 秒强视觉钩子，文字大且高对比；"
            "正文：短视频口播脚本 30s-3min，3 秒钩子+干货拉升收藏+结尾显性「建议收藏」；"
            "标题：钩子型/悬念型/反常识型，前 10 字抓眼球；互动机制：收藏、评论、转发、点赞（收藏率权重最高）。"
        ),
        "collect_keywords": "建议收藏,先收藏,收藏起来",
        "share_keywords": "转发,分享",
        "copy_min_words": 100,
        "copy_max_words": 800,
    },
    {
        "name": "视频号",
        "algorithm_weights": "社交推荐（朋友赞 > 陌生人赞）权重翻倍；评论数 > 播放 > 点赞",
        "content_prefs": "公域做流量入口（核心指标评论数）+ 私域承接；真实人设内容；月活 10.3 亿",
        "red_lines": "诱导分享、虚假人设、违规导流",
        "ai_label_required": 1,
        "best_practices": "评论区引导问题设计（二选一/报数字）；人设型标题；私域承接话术",
        "platform_spec": (
            "封面：6:7 竖版 1080×1260，真实人设出镜，社交推荐导向；"
            "正文：短视频口播脚本 30s-2min，评论区引导问题设计（二选一/报数字）；"
            "标题：人设型/提问型，朋友赞权重翻倍；互动机制：推荐（朋友赞）、评论、关注、点赞（评论数权重最高）。"
        ),
        "collect_keywords": "收藏,关注",
        "share_keywords": "推荐,转发,分享",
        "copy_min_words": 100,
        "copy_max_words": 600,
    },
    {
        "name": "公众号",
        "algorithm_weights": "完读率决定推荐；64 个流量点位（搜一搜/看一看/订阅消息等）",
        "content_prefs": "深度长文；开头 3 秒钩子；分段小标题；信息密度高",
        "red_lines": "极限词、诱导关注、抄袭洗稿",
        "ai_label_required": 1,
        "best_practices": "开头 3 秒钩子；每 300 字一个小标题；结尾互动问题；AI 辅助创作声明",
        "platform_spec": (
            "封面：头图 2.35:1（900×383），正文配图 16:9，文字不压主体；"
            "正文：深度长文 2000-4000 字，开头 3 秒钩子，每 300 字一个小标题，信息密度高，结尾互动问题；"
            "标题：数字/悬念/人群指向，订阅列表 1 屏内突出；互动机制：在看（转发）、点赞、留言、划线收藏。"
        ),
        "collect_keywords": "收藏,在看,划线",
        "share_keywords": "在看,转发,分享",
        "copy_min_words": 800,
        "copy_max_words": 3000,
    },
    {
        "name": "知乎",
        "algorithm_weights": "赞同/收藏 > 评论 > 关注（专业内容权重高）",
        "content_prefs": "专业人设沉淀；结论先行 + 分点论证；深耕 3C/健康/AI 赛道；图文注意力分流后做深度",
        "red_lines": "洗稿、虚假专业身份、营销导流",
        "ai_label_required": 1,
        "best_practices": "第一段直接给答案；引用数据/案例；结尾给延伸建议；专业但不说教",
        "platform_spec": (
            "封面：头图 16:9 或信息图，问题页首图；"
            "正文：回答体 800-2500 字，结论先行第一段直接给答案，分点论证，引用数据/案例，结尾延伸建议；"
            "标题：问题型/结论型，专业但不说教；互动机制：赞同、收藏、评论、关注（专业内容权重高）。"
        ),
        "collect_keywords": "收藏,赞同",
        "share_keywords": "转发,分享",
        "copy_min_words": 500,
        "copy_max_words": 3000,
    },
    {
        "name": "问一问",
        "algorithm_weights": "流量扶持红利期；奖励图片好看 + 信息密度高 + 实用内容",
        "content_prefs": "开头直接给答案（2句内）；每条建议独立成段；配图位标注；可直接收藏",
        "red_lines": "答非所问、纯引流、低质灌水",
        "ai_label_required": 0,
        "best_practices": "答案结构清晰可直接收藏；图文并茂；靠广告曝光分成变现；冷启动渠道",
        "platform_spec": (
            "封面：配图位标注，图文并茂，信息密度高；"
            "正文：答案体 200-800 字，开头 2 句内直接给答案，每条建议独立成段，可直接收藏；"
            "标题：问题型/直接答案型；互动机制：赞同、收藏、评论（曝光分成变现）。"
        ),
        "collect_keywords": "收藏,赞同",
        "share_keywords": "转发,分享",
        "copy_min_words": 200,
        "copy_max_words": 800,
    },
]


def get_default_rules() -> list:
    """返回默认规则卡副本（避免外部修改污染种子数据）。"""
    return [dict(rule) for rule in CHANNEL_RULES]
