"""
6 平台规则库（M3 渠道中心核心资产）。

规则卡结构：
- algorithm_weights: 算法权重排序（调研报告 2026 口径）
- content_prefs: 内容偏好
- red_lines: 平台红线
- ai_label_required: 是否强制 AI 标注
- best_practices: 最佳实践（可直接指导改写）

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
    },
    {
        "name": "抖音",
        "algorithm_weights": "收藏率 > 复访率 > 铁粉互动 > 5秒完播 > 完播率 > 点赞/评论 > 转发（2026 新规）",
        "content_prefs": "干货拉升收藏；真实案例；3秒钩子；显性「建议收藏」指令；7天长效赛马",
        "red_lines": "稀缺逼单、虚假价格、售后承诺、虚假权威",
        "ai_label_required": 1,
        "best_practices": "前 5 秒强钩子；结尾显性收藏指令；行动指令不能只靠暗示；评论区置顶引导收藏",
    },
    {
        "name": "视频号",
        "algorithm_weights": "社交推荐（朋友赞 > 陌生人赞）权重翻倍；评论数 > 播放 > 点赞",
        "content_prefs": "公域做流量入口（核心指标评论数）+ 私域承接；真实人设内容；月活 10.3 亿",
        "red_lines": "诱导分享、虚假人设、违规导流",
        "ai_label_required": 1,
        "best_practices": "评论区引导问题设计（二选一/报数字）；人设型标题；私域承接话术",
    },
    {
        "name": "公众号",
        "algorithm_weights": "完读率决定推荐；64 个流量点位（搜一搜/看一看/订阅消息等）",
        "content_prefs": "深度长文；开头 3 秒钩子；分段小标题；信息密度高",
        "red_lines": "极限词、诱导关注、抄袭洗稿",
        "ai_label_required": 1,
        "best_practices": "开头 3 秒钩子；每 300 字一个小标题；结尾互动问题；AI 辅助创作声明",
    },
    {
        "name": "知乎",
        "algorithm_weights": "赞同/收藏 > 评论 > 关注（专业内容权重高）",
        "content_prefs": "专业人设沉淀；结论先行 + 分点论证；深耕 3C/健康/AI 赛道；图文注意力分流后做深度",
        "red_lines": "洗稿、虚假专业身份、营销导流",
        "ai_label_required": 1,
        "best_practices": "第一段直接给答案；引用数据/案例；结尾给延伸建议；专业但不说教",
    },
    {
        "name": "问一问",
        "algorithm_weights": "流量扶持红利期；奖励图片好看 + 信息密度高 + 实用内容",
        "content_prefs": "开头直接给答案（2句内）；每条建议独立成段；配图位标注；可直接收藏",
        "red_lines": "答非所问、纯引流、低质灌水",
        "ai_label_required": 0,
        "best_practices": "答案结构清晰可直接收藏；图文并茂；靠广告曝光分成变现；冷启动渠道",
    },
]


def get_default_rules() -> list:
    """返回默认规则卡副本（避免外部修改污染种子数据）。"""
    return [dict(rule) for rule in CHANNEL_RULES]
