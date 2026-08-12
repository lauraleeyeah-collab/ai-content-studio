"""
Agent7: 热门内容趋势分析
代码计算趋势统计数据,LLM识别模式与趋势。
"""
import json
import random
import re
from collections import Counter
from itertools import combinations

from config import TEMPERATURE_CONFIG, MAX_TREND_NOTES_FOR_LLM
from prompts import trend_summary_prompt
from utils.llm_client import call_llm_json
from utils.prompt_utils import render


def _total_engagement(note: dict) -> int:
    return sum(note.get(k, 0) or 0 for k in ("likes", "comments", "collects", "shares"))


def _classify_title(title: str) -> str:
    """用简单正则启发式分类标题模式。"""
    if not title:
        return "其他"
    # 强信号:以数字开头 -> 数字清单型
    if re.match(r"^\d", title):
        return "数字清单型"
    # 具体的多字符模式优先(避免被宽泛的单字匹配抢走)
    if re.search(r"不要|别再|停止|千万别", title):
        return "痛点型"
    if re.search(r"居然|竟然|没想到|其实", title):
        return "反常识型"
    if re.search(r"教程|攻略|方法|步骤|如何", title):
        return "教程型"
    if "？" in title or "?" in title:
        return "疑问型"
    # 弱信号:包含量词 -> 数字清单型(放在最后,避免误伤)
    if re.search(r"[个条种步]", title):
        return "数字清单型"
    return "其他"


def _compute_trend_stats(notes: list) -> dict:
    """纯代码计算趋势统计数据。"""
    if not notes:
        return {"total_notes": 0}

    total = len(notes)

    # 互动量列表
    engagements = [_total_engagement(n) for n in notes]

    # 互动分布直方图(5个桶)
    buckets = {"0-100": 0, "100-500": 0, "500-2000": 0, "2000-10000": 0, "10000+": 0}
    for e in engagements:
        if e < 100:
            buckets["0-100"] += 1
        elif e < 500:
            buckets["100-500"] += 1
        elif e < 2000:
            buckets["500-2000"] += 1
        elif e < 10000:
            buckets["2000-10000"] += 1
        else:
            buckets["10000+"] += 1

    # 标签频率 Top 20
    all_tags = []
    tag_sets = []
    for n in notes:
        tags = n.get("hashtags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        if isinstance(tags, list):
            all_tags.extend(tags)
            tag_sets.append(set(tags))
    hashtag_frequency = [{"tag": t, "count": c} for t, c in Counter(all_tags).most_common(20)]

    # 标签共现 Top 10
    cooccurrence = Counter()
    for tag_set in tag_sets:
        if len(tag_set) >= 2:
            for pair in combinations(sorted(tag_set), 2):
                cooccurrence[pair] += 1
    hashtag_cooccurrence = [
        {"pair": list(p), "count": c}
        for p, c in cooccurrence.most_common(10)
    ]

    # 内容形式比例(归一化到三个标准key)
    _format_map = {"视频": "视频笔记", "视频笔记": "视频笔记", "图文": "图文笔记", "图文笔记": "图文笔记"}
    format_counter = Counter()
    for n in notes:
        raw_type = (n.get("note_type") or "未知").strip()
        format_counter[_format_map.get(raw_type, "未知")] += 1
    content_format_ratio = {
        "视频笔记": format_counter.get("视频笔记", 0),
        "图文笔记": format_counter.get("图文笔记", 0),
        "未知": format_counter.get("未知", 0),
    }

    # 标题/正文长度
    title_lengths = [len(n.get("title", "")) for n in notes]
    body_lengths = [len(n.get("body_text", "")) for n in notes]
    avg_title_length = round(sum(title_lengths) / total, 1) if title_lengths else 0
    avg_body_length = round(sum(body_lengths) / total, 1) if body_lengths else 0

    # 标题公式频率
    title_formulas = Counter(_classify_title(n.get("title", "")) for n in notes)
    title_formula_frequency = dict(title_formulas)

    # 按形式分类的平均互动
    engagement_by_type = {}
    for fmt in ("视频笔记", "图文笔记", "未知"):
        type_notes = [
            n for n in notes
            if _format_map.get((n.get("note_type") or "未知").strip(), "未知") == fmt
        ]
        if type_notes:
            engagement_by_type[fmt] = round(
                sum(_total_engagement(n) for n in type_notes) / len(type_notes), 1
            )

    # 90分位爆款阈值
    sorted_engagements = sorted(engagements)
    idx_90 = int(len(sorted_engagements) * 0.9)
    high_engagement_threshold = sorted_engagements[min(idx_90, len(sorted_engagements) - 1)]

    # 高互动笔记
    high_notes = [
        {
            "title": n.get("title", ""),
            "total_engagement": _total_engagement(n),
            "note_type": n.get("note_type", "未知"),
            "hashtags": n.get("hashtags", []),
        }
        for n in notes
        if _total_engagement(n) >= high_engagement_threshold
    ]
    high_notes.sort(key=lambda x: x["total_engagement"], reverse=True)

    return {
        "total_notes": total,
        "engagement_distribution": buckets,
        "hashtag_frequency": hashtag_frequency,
        "hashtag_cooccurrence": hashtag_cooccurrence,
        "content_format_ratio": content_format_ratio,
        "avg_title_length": avg_title_length,
        "avg_body_length": avg_body_length,
        "title_formula_frequency": title_formula_frequency,
        "engagement_by_format": engagement_by_type,
        "high_engagement_threshold": high_engagement_threshold,
        "high_engagement_notes": high_notes,
        "avg_engagement": round(sum(engagements) / total, 1),
    }


def summarize_trends(track: str, structured_notes: list, time_range: str) -> dict:
    """
    分析赛道内容趋势。

    Args:
        track: 赛道关键词
        structured_notes: 结构化笔记列表
        time_range: 时间范围描述

    Returns:
        {"computed_stats": {...}, "llm_summary": {...}}
    """
    computed_stats = _compute_trend_stats(structured_notes)

    # 采样发送给LLM
    if len(structured_notes) > MAX_TREND_NOTES_FOR_LLM:
        sampled = random.sample(structured_notes, MAX_TREND_NOTES_FOR_LLM)
    else:
        sampled = structured_notes

    high_notes = computed_stats.get("high_engagement_notes", [])[:10]
    high_notes_str = json.dumps(high_notes, ensure_ascii=False, indent=2)

    # 统计数据(去掉高互动笔记详情,已在单独字段发送)
    stats_for_llm = {k: v for k, v in computed_stats.items() if k != "high_engagement_notes"}
    stats_str = json.dumps(stats_for_llm, ensure_ascii=False, indent=2)

    # 全部笔记概览(带采样的详细内容)
    note_lines = []
    for i, note in enumerate(sampled, 1):
        title = note.get("title", "(无标题)")
        body = (note.get("body_text") or "")[:200]
        tags = ", ".join(note.get("hashtags") or []) if isinstance(note.get("hashtags"), list) else (note.get("hashtags") or "")
        eng = _total_engagement(note)
        nt = note.get("note_type", "未知")
        note_lines.append(
            f"[{i}] 标题:{title}\n"
            f"    形式:{nt} | 总互动:{eng}\n"
            f"    正文摘要:{body}\n"
            f"    标签:{tags}"
        )
    all_notes_summary = (
        f"共{len(structured_notes)}条笔记,采样{len(sampled)}条展示如下:\n"
        + "\n".join(note_lines)
    )

    user_prompt = render(
        trend_summary_prompt.USER_PROMPT_TEMPLATE,
        track=track,
        time_range=time_range,
        computed_stats=stats_str,
        high_engagement_notes=high_notes_str,
        all_notes_summary=all_notes_summary,
    )

    llm_summary = call_llm_json(
        system_prompt=trend_summary_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["trend_summarizer"],
        max_tokens=3000,
    )

    return {
        "computed_stats": computed_stats,
        "llm_summary": llm_summary,
    }
