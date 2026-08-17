"""
内容生产报告生成器（工作台延伸）。

一键串联 M1 图文工厂 → M2 视频工厂 → M3 渠道中心的完整生产链路，
输出一份可交付的内容生产报告（Markdown），可直接用于作品集与面试演示。
"""
import json

from agents.search_keyword_analyzer import analyze_search_keywords
from agents.title_optimizer import generate_title_variants
from agents.cover_prompt_generator import generate_cover_prompt
from agents.platform_copywriter import rewrite_for_channel
from agents.interaction_copywriter import generate_interaction_copy
from agents.video_script_storyboarder import generate_video_script
from agents.video_play_optimizer import optimize_video_play
from agents.channel_rewriter import rewrite_multi_channel, ALL_CHANNELS
from utils.rule_checks import check_title_keywords

DEFAULT_CHANNELS = ["小红书", "抖音", "视频号"]
REPORT_DURATION = 60


def build_content_report(
    track: str,
    topic_title: str,
    topic_angle: str,
    source_content: str,
    persona_description: str,
    channels: list = None,
) -> dict:
    """
    一键生成完整内容生产报告。

    返回：
    {
        topic: {title, angle},
        search_keywords, titles, cover, copy, interaction,
        script, play, channel_versions, compliance, ai_labels,
        report_markdown
    }
    """
    channels = channels or DEFAULT_CHANNELS
    if not all(c in ALL_CHANNELS for c in channels):
        raise ValueError(f"渠道必须在 {ALL_CHANNELS} 内")

    # M1 图文链路
    keywords = analyze_search_keywords(track, topic_title, topic_angle, persona_description)
    kw_list = [k["keyword"] for k in keywords]
    kw_text = "、".join(kw_list[:3])

    titles = generate_title_variants(track, topic_title, topic_angle, persona_description, 5)
    for t in titles:
        t["keyword_check"] = check_title_keywords(t.get("title", ""), kw_list)

    cover = generate_cover_prompt(track, topic_title, "小红书", "图文笔记", kw_text)
    copy = rewrite_for_channel(track, topic_title, "小红书", source_content, keywords, persona_description)
    interaction = generate_interaction_copy(track, topic_title, "小红书", copy.get("content", ""))

    # M2 视频链路
    script = generate_video_script(track, topic_title, topic_angle, "抖音", REPORT_DURATION, keywords, persona_description)
    play = optimize_video_play(track, topic_title, "抖音", REPORT_DURATION,
                               json.dumps(script.get("storyboard", []), ensure_ascii=False))

    # M3 渠道链路
    channel_versions = rewrite_multi_channel(topic_title, source_content, channels, keywords, persona_description)

    compliance_results = {}
    for rw in channel_versions:
        ch = rw.get("channel", "")
        compliance_results[ch] = {
            "red_lines": rw.get("code_checks", {}).get("red_lines", {}),
            "ai_label": rw.get("ai_label", {}),
        }

    report = {
        "topic": {"title": topic_title, "angle": topic_angle},
        "search_keywords": keywords,
        "titles": titles,
        "cover": cover,
        "copy": copy,
        "interaction": interaction,
        "script": script,
        "play": play,
        "channel_versions": channel_versions,
        "compliance": compliance_results,
        "duration_seconds": REPORT_DURATION,
    }
    report["report_markdown"] = render_report_markdown(report, track, persona_description)
    return report


def render_report_markdown(report: dict, track: str = "", persona_description: str = "") -> str:
    """把生产报告渲染为 Markdown（作品集可交付物）。"""
    topic = report.get("topic", {})
    lines = [
        "# 内容生产报告",
        "",
        f"**选题：** {topic.get('title', '')}",
        f"**角度：** {topic.get('angle', '')}",
        f"**赛道：** {track or '-'}",
        "",
        "## 一、搜索词策略",
        "",
    ]
    for k in report.get("search_keywords", []):
        tag = "（长尾）" if k.get("is_long_tail") else ""
        lines.append(f"- `{k.get('keyword')}`：{k.get('search_intent')}，优先级 {k.get('priority')}{tag}")
    lines.append("")

    lines += ["## 二、标题方案（前 20 字关键词检查）", ""]
    for i, t in enumerate(report.get("titles", []), 1):
        kc = t.get("keyword_check", {})
        flag = "✅" if kc.get("passed") else "⚠️"
        lines.append(f"{i}. {t.get('title')} {flag}（{t.get('formula_type')}）")
    lines.append("")

    cover = report.get("cover", {})
    lines += [
        "## 三、封面提示词",
        "",
        f"- 主体：{cover.get('subject', '')}",
        f"- 文字位：{cover.get('text_slot', '')}",
        f"- 风格：{cover.get('style', '')}",
        "",
    ]

    copy = report.get("copy", {})
    lines += [
        "## 四、图文正文（小红书示例）",
        "",
        copy.get("content", ""),
        "",
        f"结构：{copy.get('structure_note', '-')}",
        "",
    ]

    interaction = report.get("interaction", {})
    lines += ["## 五、互动话术", ""]
    for r in interaction.get("collect_reasons", []):
        lines.append(f"- 收藏理由：{r}")
    for g in interaction.get("comment_guides", []):
        lines.append(f"- 评论引导：{g}")
    lines.append("")

    script = report.get("script", {})
    lines += [f"## 六、视频分镜（{report.get('duration_seconds', 60)}s）", ""]
    for shot in script.get("storyboard", []):
        lines.append(
            f"- `{shot.get('time_start')}s-{shot.get('time_end')}s` {shot.get('scene', '')}｜"
            f"{shot.get('voiceover', '')}"
        )
    lines.append(f"- 结尾 CTA：{script.get('closing_cta', '')}")
    lines.append("")

    play = report.get("play", {})
    lines += [
        "## 七、播放优化",
        "",
        f"- 5 秒钩子：{play.get('five_sec_hook', '')}",
        f"- 收藏指令：{play.get('collect_cta', '')}",
        "",
    ]

    lines += ["## 八、多平台改写版本", ""]
    for rw in report.get("channel_versions", []):
        ch = rw.get("channel", "")
        lines += [f"### {ch}", "", rw.get("content", ""), ""]
        for reason in rw.get("rewrite_reasons", []):
            lines.append(f"- 改写理由：{reason}")
        lines.append("")

    lines += ["## 九、合规与 AI 标注", ""]
    for ch, comp in report.get("compliance", {}).items():
        rl = comp.get("red_lines", {})
        ai = comp.get("ai_label", {})
        status = "✅ 通过" if rl.get("passed") else "⚠️ 需处理"
        lines.append(f"- {ch}：红线 {status}；AI 标注：{ai.get('template', '-')}")
    lines.append("")

    lines += ["## 十、发布建议", ""]
    lines.append("- 优先发布抖音（收藏率权重第一，视频已含显性收藏指令）")
    lines.append("- 小红书标题需保证前 20 字含核心搜索词")
    lines.append("- 各平台发布时勾选 AI 创作标注")
    lines.append("")
    return "\n".join(lines)
