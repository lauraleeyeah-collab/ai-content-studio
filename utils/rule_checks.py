"""
平台规则确定性检查工具（「LLM 判断 + Python 计算」中的计算部分）。

所有检查不依赖模型，由代码确定性完成，保证可复现、可审计：
- 标题前 N 字关键词检查（小红书搜索流量超 55%，标题前 20 字需放长尾关键词）
- 正文字数校验（各平台合理区间）
- 平台红线词硬校验（极限词/导流/刷量/虚假权威，词表可持续扩展）
"""
import re

# ── 各平台图文正文字数合理区间（字符数，不含空白）──
PLATFORM_COPY_RANGES = {
    "小红书": (150, 1000),
    "公众号": (800, 3000),
    "知乎": (500, 3000),
    "问一问": (200, 800),
}

# ── 平台红线词表（基础版，M3 渠道中心可扩展）──
RED_LINE_PATTERNS = {
    "极限词": [
        "最好", "全网第一", "行业第一", "顶级", "国家级", "世界级", "史上",
        "最便宜", "最优惠", "唯一", "100%", "百分百", "绝对", "保证",
        "根治", "包治", "无效退款", "零风险", "稳赚", "必赚", "躺赚",
    ],
    "站外导流": ["加微信", "加vx", "vx:", "微信号", "公众号搜索", "点击链接", "私信我领取", "扫码进群"],
    "刷量诱导": ["点赞送", "关注私聊", "转发抽奖", "集赞", "刷评论"],
    "虚假权威": ["专家认证", "官方指定", "国家认证", "专利保证", "权威机构认证"],
}


def _count_chars(text: str) -> int:
    """统计中文字符数（去掉空白字符）。"""
    return len(re.sub(r"\s", "", text or ""))


def check_title_keywords(title: str, keywords: list, max_prefix_chars: int = 20) -> dict:
    """
    检查标题前 max_prefix_chars 字内是否命中核心关键词。

    规则：搜索流量下，标题前 20 字必须放长尾关键词。
    按关键词顺序（调用方已按优先级排序）检查前 3 个，命中任一个即通过。

    返回：
        passed: 是否通过
        matched_in_prefix: 前缀内命中的关键词
        all_present: 标题全文中出现的关键词
        missing: 标题中完全未出现的关键词
        suggestion: 未通过时的改写建议
    """
    title = title or ""
    prefix = title[:max_prefix_chars]
    top_keywords = [k for k in (keywords or []) if k][:3]

    matched_in_prefix = [k for k in top_keywords if k in prefix]
    all_present = [k for k in top_keywords if k in title]
    missing = [k for k in top_keywords if k not in title]

    # 无关键词可检查时视为通过（不误报），有检查项但未命中前缀才判失败
    passed = (not top_keywords) or len(matched_in_prefix) > 0
    suggestion = ""
    if not passed and top_keywords:
        target = top_keywords[0]
        suggestion = f"建议把核心关键词「{target}」放在标题前 {max_prefix_chars} 字内，例如将「{target}」作为开头。"

    return {
        "passed": passed,
        "matched_in_prefix": matched_in_prefix,
        "all_present": all_present,
        "missing": missing,
        "prefix_chars": max_prefix_chars,
        "suggestion": suggestion,
    }


def check_copy_word_count(text: str, channel: str, tolerance: int = 100) -> dict:
    """
    校验正文长度是否在平台合理区间（±tolerance 容忍）。
    不满足时给出建议方向，不拦截（正文长短由创作意图决定）。
    """
    channel = channel if channel in PLATFORM_COPY_RANGES else "小红书"
    min_words, max_words = PLATFORM_COPY_RANGES[channel]
    chars = _count_chars(text)

    status = "ok"
    suggestion = ""
    if chars < min_words - tolerance:
        status = "too_short"
        suggestion = f"正文偏短（{chars} 字），{channel} 建议 {min_words}-{max_words} 字，可补充步骤细节或案例。"
    elif chars > max_words + tolerance:
        status = "too_long"
        suggestion = f"正文偏长（{chars} 字），{channel} 建议 {min_words}-{max_words} 字，可拆分系列或精简表达。"

    return {
        "channel": channel,
        "chars": chars,
        "min_words": min_words,
        "max_words": max_words,
        "status": status,
        "suggestion": suggestion,
    }


def scan_red_lines(text: str) -> dict:
    """
    红线词硬校验：命中任一平台红线词即返回告警。
    返回：{passed, hits: [{category, word}], suggestion}
    """
    text = text or ""
    hits = []
    for category, words in RED_LINE_PATTERNS.items():
        for word in words:
            if word in text:
                hits.append({"category": category, "word": word})

    return {
        "passed": len(hits) == 0,
        "hits": hits,
        "suggestion": "命中红线词，请改写后再发布。" if hits else "",
    }


def check_cover_prompt_completeness(prompt: dict) -> dict:
    """
    封面提示词完整性校验：必填字段缺失即标记，避免生成不可用的封面。
    必填：subject(主体/内容), style(风格), composition(构图), text_slot(文字位)。
    """
    required = ["subject", "style", "composition", "text_slot"]
    missing = [k for k in required if not (prompt or {}).get(k)]
    return {
        "passed": len(missing) == 0,
        "missing": missing,
        "suggestion": f"封面提示词缺少字段：{', '.join(missing)}，请补充后再用于生图。" if missing else "",
    }
