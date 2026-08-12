"""
平台工作台生产器（按社交媒体切分核心）。

每个平台（小红书 / 公众号 / 知乎）一个专属工作台：
选题角度 → 标题方案 → 封面提示词 → 平台正文 → 互动策略，
输出平台专属生产报告。LLM 负责按平台规则生成，Python 负责
关键词检查、封面规格、字数、互动引导等确定性兜底。
"""
from prompts import platform_workshop_prompt
from database.channel_rules import get_default_rules
from utils.llm_client import call_llm_json
from utils.rule_checks import check_title_keywords, check_copy_word_count
from config import TEMPERATURE_CONFIG
from agents.search_keyword_analyzer import analyze_search_keywords

PLATFORMS = ["小红书", "公众号", "知乎"]

PLATFORM_SPECS = {
    "小红书": (
        "封面：3:4 竖版 1080×1440，人物/产品居中偏右，顶部 1/3 留文字位，文字大且高对比；"
        "正文：清单体/步骤体 800-1500 字，搜索关键词前置，结尾显性收藏指令；"
        "标题：前 20 字放长尾关键词；互动机制：收藏、评论、转发、点赞（收藏权重最高）。"
    ),
    "公众号": (
        "封面：头图 2.35:1（900×383），正文配图 16:9，文字不压主体；"
        "正文：深度长文 2000-4000 字，开头 3 秒钩子，每 300 字一个小标题，信息密度高，结尾互动问题；"
        "标题：数字/悬念/人群指向，订阅列表 1 屏内突出；互动机制：在看（转发）、点赞、留言、划线收藏。"
    ),
    "知乎": (
        "封面：头图 16:9 或信息图，问题页首图；"
        "正文：回答体 800-2500 字，结论先行第一段直接给答案，分点论证，引用数据/案例，结尾延伸建议；"
        "标题：问题型/结论型，专业但不说教；互动机制：赞同、收藏、评论、关注（专业内容权重高）。"
    ),
}

# 平台互动引导检查：必须命中至少一条显性行动指令
COLLECT_KEYWORDS = {
    "小红书": ["收藏"],
    "公众号": ["收藏", "在看", "划线"],
    "知乎": ["收藏", "赞同"],
}
SHARE_KEYWORDS = {
    "小红书": ["转发", "分享", "发给"],
    "公众号": ["在看", "转发", "分享"],
    "知乎": ["转发", "分享"],
}


def _get_rule_card(platform: str) -> str:
    """从平台规则库取规则卡文本。"""
    for rule in get_default_rules():
        if rule["name"] == platform:
            return (
                f"算法权重：{rule['algorithm_weights']}\n"
                f"内容偏好：{rule['content_prefs']}\n"
                f"红线：{rule['red_lines']}\n"
                f"最佳实践：{rule['best_practices']}"
            )
    return "无规则卡"


def _check_interaction_guides(platform: str, interaction: dict) -> dict:
    """互动策略确定性检查：收藏/分享/评论引导是否齐全。"""
    collect_reasons = interaction.get("collect_reasons", []) or []
    share_guides = interaction.get("share_guides", []) or []
    comment_guides = interaction.get("comment_guides", []) or []
    cta = " ".join(interaction.get("cta_suggestions", []) or []) or ""

    kw = COLLECT_KEYWORDS.get(platform, [])
    collect_hit = any(k in (t + cta) for k in kw for t in collect_reasons) or any(k in cta for k in kw)
    share_hit = any(k in (s + cta) for k in SHARE_KEYWORDS.get(platform, []) for s in share_guides)

    return {
        "collect_cta": {
            "passed": collect_hit,
            "detail": "含收藏/划线引导" if collect_hit else "缺少显性收藏引导，建议补充「建议收藏」",
        },
        "share_cta": {
            "passed": share_hit,
            "detail": "含转发/在看引导" if share_hit else "缺少转发/分享引导，建议补充",
        },
        "comment_guides": {
            "passed": len(comment_guides) >= 2,
            "detail": f"评论区引导 {len(comment_guides)} 条",
        },
    }


def produce_for_platform(
    platform: str,
    track: str,
    topic_title: str,
    topic_angle: str = "",
    source_content: str = "",
    persona_description: str = "",
) -> dict:
    """
    平台专属一键生产。

    返回：
    {
        platform, topic, search_keywords, titles, cover, copy,
        interaction, topic_angles, rule_card, platform_spec,
        checks: {titles, copy_word_count, interaction},
        platform_markdown
    }
    """
    if platform not in PLATFORMS:
        raise ValueError(f"平台必须是 {PLATFORMS} 之一，当前: {platform}")

    # 1. 搜索词（复用 M1 确定性兜底）
    keywords = analyze_search_keywords(track, topic_title, topic_angle, persona_description)
    kw_list = [k["keyword"] for k in keywords]

    # 2. LLM 平台生产
    system_prompt = platform_workshop_prompt.SYSTEM_PROMPT.format(
        platform=platform,
        rule_card=_get_rule_card(platform),
        platform_spec=PLATFORM_SPECS[platform],
    )
    user_prompt = platform_workshop_prompt.USER_PROMPT_TEMPLATE.format(
        platform=platform,
        track=track or "未指定",
        topic_title=topic_title,
        topic_angle=topic_angle or "未指定",
        source_content=source_content or "（无素材，请基于选题经验补全）",
        persona_description=persona_description or "未提供",
    )
    result = call_llm_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG.get("platform_workshop", 0.6),
        max_tokens=3000,
    )
    if not isinstance(result, dict):
        raise ValueError("平台生产返回结果格式异常，预期是对象")

    # 3. 确定性兜底
    titles = result.get("titles", [])[:5] or []
    for t in titles:
        t["keyword_check"] = check_title_keywords(t.get("title", ""), kw_list)

    cover = result.get("cover", {}) or {}
    cover.setdefault("spec_note", "")
    cover["platform_spec"] = PLATFORM_SPECS[platform]

    copy = result.get("copy", {}) or {}
    copy_text = copy.get("content", "")
    copy["word_count"] = check_copy_word_count(copy_text, platform)

    interaction = result.get("interaction", {}) or {}
    interaction_checks = _check_interaction_guides(platform, interaction)

    topic_angles = result.get("topic_angles", [])[:3] or []

    report = {
        "platform": platform,
        "topic": {"title": topic_title, "angle": topic_angle},
        "search_keywords": keywords,
        "titles": titles,
        "cover": cover,
        "copy": copy,
        "interaction": interaction,
        "topic_angles": topic_angles,
        "rule_card": _get_rule_card(platform),
        "platform_spec": PLATFORM_SPECS[platform],
        "checks": {
            "titles": [t.get("keyword_check", {}) for t in titles],
            "copy_word_count": copy.get("word_count", {}),
            "interaction": interaction_checks,
        },
    }
    report["platform_markdown"] = render_platform_markdown(report, track, persona_description)
    return report


def render_platform_markdown(report: dict, track: str = "", persona_description: str = "") -> str:
    """平台专属生产报告 Markdown（作品集可交付物）。"""
    platform = report["platform"]
    lines = [
        f"# {platform} 平台生产报告",
        "",
        f"**赛道：** {track or '-'}",
        f"**选题：** {report['topic']['title']}",
        f"**人设：** {persona_description or '-'}",
        "",
        "## 一、选题角度建议",
        "",
    ]
    for i, a in enumerate(report.get("topic_angles", []), 1):
        lines.append(f"{i}. **{a.get('angle')}**：{a.get('rationale', '')}")
    lines += ["", "## 二、标题方案", ""]
    for t in report.get("titles", []):
        flag = "✅" if t.get("keyword_check", {}).get("passed") else "⚠️ 关键词未前置"
        lines.append(f"- {t.get('title')}（{t.get('formula_type', '')}）{flag}")
    lines += ["", "## 三、封面提示词", ""]
    cover = report.get("cover", {})
    lines.append(f"- **主体：** {cover.get('subject', '')}")
    lines.append(f"- **风格：** {cover.get('style', '')}")
    lines.append(f"- **构图：** {cover.get('composition', '')}")
    lines.append(f"- **文字位：** {cover.get('text_slot', '')}")
    lines.append(f"- **规格：** {cover.get('spec_note', '')}")
    lines += ["", "## 四、平台正文", ""]
    lines.append(report.get("copy", {}).get("content", ""))
    lines.append("")
    lines.append(f"> 结构说明：{report.get('copy', {}).get('structure_note', '')}")
    lines += ["", "## 五、互动策略", ""]
    inter = report.get("interaction", {})
    lines.append("**收藏/划线理由：**")
    for r in inter.get("collect_reasons", []):
        lines.append(f"- {r}")
    lines.append("")
    lines.append("**转发/分享引导：**")
    for r in inter.get("share_guides", []):
        lines.append(f"- {r}")
    lines.append("")
    lines.append("**评论区引导：**")
    for r in inter.get("comment_guides", []):
        lines.append(f"- {r}")
    lines.append("")
    lines.append(f"**策略说明：** {inter.get('strategy_note', '')}")
    lines += ["", "## 六、平台规则卡", ""]
    lines.append(report.get("rule_card", "").replace("\n", "\n\n"))
    return "\n".join(lines)
