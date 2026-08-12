"""
Agent: 竞品账号分析Agent
对竞品账号的笔记数据进行定量统计 + LLM定性分析,输出完整的分析报告。
"""
import json
import random
from collections import Counter
from datetime import datetime

from config import TEMPERATURE_CONFIG, MAX_ACCOUNT_NOTES_FOR_LLM
from prompts import account_analysis_prompt
from utils.llm_client import call_llm_json
from utils.prompt_utils import render


# ── 日期解析工具 ──

_DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y年%m月%d日",
    "%Y.%m.%d",
    "%m-%d",
    "%m/%d",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
]


def _parse_date(date_str):
    """尝试多种格式解析日期,返回datetime或None。"""
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip()
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(date_str, fmt)
            # 对于没有年份的格式(如"03-15"),补充当前年份
            if dt.year == 1900:
                dt = dt.replace(year=datetime.now().year)
            return dt
        except ValueError:
            continue
    return None


def _total_engagement(note: dict) -> int:
    """计算单条笔记的总互动量(likes+comments+collects+shares)。"""
    total = 0
    for key in ("likes", "comments", "collects", "shares"):
        val = note.get(key)
        if val is not None:
            try:
                total += int(val)
            except (ValueError, TypeError):
                pass
    return total


def _map_note_type(raw_type) -> str:
    """将笔记类型统一映射到标准名称。"""
    if not raw_type:
        return "未知"
    raw_type = str(raw_type).strip()
    if raw_type in ("视频", "视频笔记"):
        return "视频笔记"
    if raw_type in ("图文", "图文笔记"):
        return "图文笔记"
    return "未知"


# ── 核心统计计算 ──

def _compute_account_stats(notes: list, fans_count: int = 0) -> dict:
    """
    根据笔记列表计算所有定量统计指标。

    notes: 结构化笔记列表(每条包含 title, likes, comments, collects, shares,
           post_date, note_type, hashtags 等字段)
    fans_count: 账号粉丝数,用于计算互动率

    Returns:
        包含所有统计字段的字典:
        - total_notes, date_range, posting_frequency
        - avg_likes, avg_comments, avg_collects, avg_shares
        - engagement_rate, content_type_distribution
        - top_hashtags, posting_time_pattern, engagement_trend
        - best_performing_notes, worst_performing_notes
    """
    if not notes:
        return {
            "total_notes": 0,
            "date_range": "无数据",
            "posting_frequency": 0,
            "avg_likes": 0,
            "avg_comments": 0,
            "avg_collects": 0,
            "avg_shares": 0,
            "engagement_rate": 0,
            "content_type_distribution": {},
            "top_hashtags": [],
            "posting_time_pattern": {"weekday": 0, "weekend": 0},
            "engagement_trend": {"slope": 0, "direction": "stable"},
            "best_performing_notes": [],
            "worst_performing_notes": [],
        }

    total = len(notes)
    stats = {"total_notes": total}

    # ── 日期范围 & 发布频率 ──
    parsed_dates = []
    for n in notes:
        dt = _parse_date(n.get("post_date"))
        if dt:
            parsed_dates.append(dt)

    if len(parsed_dates) >= 2:
        earliest = min(parsed_dates)
        latest = max(parsed_dates)
        stats["date_range"] = f"{earliest.strftime('%Y-%m-%d')} ~ {latest.strftime('%Y-%m-%d')}"
        days_span = max((latest - earliest).days, 1)
        weeks_span = max(days_span / 7.0, 1.0)
        stats["posting_frequency"] = round(total / weeks_span, 2)
    elif len(parsed_dates) == 1:
        stats["date_range"] = parsed_dates[0].strftime("%Y-%m-%d")
        stats["posting_frequency"] = 0
    else:
        stats["date_range"] = "无法解析日期"
        stats["posting_frequency"] = 0

    # ── 平均互动数据 ──
    for key in ("likes", "comments", "collects", "shares"):
        values = []
        for n in notes:
            val = n.get(key)
            if val is not None:
                try:
                    values.append(int(val))
                except (ValueError, TypeError):
                    pass
        avg = round(sum(values) / len(values), 1) if values else 0
        stats[f"avg_{key}"] = avg

    # ── 互动率 ──
    total_interactions = sum(_total_engagement(n) for n in notes)
    if fans_count and fans_count > 0:
        stats["engagement_rate"] = round(total_interactions / fans_count * 100, 2)
    else:
        stats["engagement_rate"] = 0

    # ── 内容类型分布(映射到标准名称) ──
    type_dist = {"视频笔记": 0, "图文笔记": 0, "未知": 0}
    for n in notes:
        mapped = _map_note_type(n.get("note_type"))
        type_dist[mapped] = type_dist.get(mapped, 0) + 1
    stats["content_type_distribution"] = type_dist

    # ── Top 15 Hashtags(按频率排序) ──
    all_tags = []
    for n in notes:
        tags = n.get("hashtags") or []
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
        if isinstance(tags, list):
            for tag in tags:
                tag = str(tag).strip()
                if tag:
                    all_tags.append(tag)
    tag_counts = Counter(all_tags)
    stats["top_hashtags"] = [
        {"tag": t, "count": c} for t, c in tag_counts.most_common(15)
    ]

    # ── 发布时间模式(工作日 vs 周末) ──
    weekday_count = 0
    weekend_count = 0
    for dt in parsed_dates:
        if dt.weekday() < 5:
            weekday_count += 1
        else:
            weekend_count += 1
    stats["posting_time_pattern"] = {"weekday": weekday_count, "weekend": weekend_count}

    # ── 互动趋势(线性回归,使用日期ordinal) ──
    # 将日期转为ordinal,对每条笔记的总互动量做简单线性回归
    # 使用公式: slope = (n*sum(xy) - sum(x)*sum(y)) / (n*sum(x^2) - (sum(x))^2)
    engagement_points = []
    for i, n in enumerate(notes):
        dt = _parse_date(n.get("post_date"))
        eng = _total_engagement(n)
        if dt:
            engagement_points.append((dt.toordinal(), eng))
        else:
            # 无日期的笔记用序号作为x轴近似
            engagement_points.append((i, eng))

    n_pts = len(engagement_points)
    if n_pts >= 2:
        sum_x = sum(p[0] for p in engagement_points)
        sum_y = sum(p[1] for p in engagement_points)
        sum_xy = sum(p[0] * p[1] for p in engagement_points)
        sum_x2 = sum(p[0] * p[0] for p in engagement_points)

        denom = n_pts * sum_x2 - sum_x * sum_x
        if denom != 0:
            slope = (n_pts * sum_xy - sum_x * sum_y) / denom
        else:
            slope = 0.0

        # 判断方向:斜率相对于平均互动的比例
        mean_engagement = sum_y / n_pts if n_pts > 0 else 1
        if mean_engagement > 0:
            relative_slope = slope / mean_engagement
        else:
            relative_slope = 0

        if relative_slope > 0.005:
            direction = "rising"
        elif relative_slope < -0.005:
            direction = "declining"
        else:
            direction = "stable"

        stats["engagement_trend"] = {"slope": round(slope, 4), "direction": direction}
    else:
        stats["engagement_trend"] = {"slope": 0, "direction": "stable"}

    # ── 最佳/最差笔记 Top 3 ──
    ranked = sorted(notes, key=_total_engagement, reverse=True)

    def _note_summary(n):
        return {
            "title": n.get("title", "无标题"),
            "total_engagement": _total_engagement(n),
            "likes": n.get("likes"),
            "comments": n.get("comments"),
            "collects": n.get("collects"),
            "shares": n.get("shares"),
        }

    stats["best_performing_notes"] = [_note_summary(n) for n in ranked[:3]]
    if len(ranked) >= 3:
        stats["worst_performing_notes"] = [_note_summary(n) for n in ranked[-3:]]
    else:
        stats["worst_performing_notes"] = [_note_summary(n) for n in ranked]

    return stats


def _sample_notes_for_llm(notes: list, max_count: int) -> list:
    """
    从全部笔记中采样发送给LLM的子集,兼顾高互动、近期、随机多样性。

    策略: top 5 by engagement + 5 most recent + 5 random from remainder, 去重。
    """
    if len(notes) <= max_count:
        return notes

    selected_ids = set()
    selected = []

    def _add(note):
        nid = id(note)
        if nid not in selected_ids:
            selected_ids.add(nid)
            selected.append(note)

    # 1) Top 5 by engagement
    by_engagement = sorted(notes, key=_total_engagement, reverse=True)
    for n in by_engagement[:5]:
        _add(n)

    # 2) 5 most recent by post_date
    def _date_key(n):
        dt = _parse_date(n.get("post_date"))
        return dt if dt else datetime.min

    by_date = sorted(notes, key=_date_key, reverse=True)
    for n in by_date[:5]:
        _add(n)

    # 3) 5 random from remainder
    remainder = [n for n in notes if id(n) not in selected_ids]
    if remainder:
        random_sample = random.sample(remainder, min(5, len(remainder)))
        for n in random_sample:
            _add(n)

    return selected[:max_count]


def analyze_account(track: str, account_info: dict, notes: list) -> dict:
    """
    对竞品账号进行全面分析:代码计算统计指标 + LLM定性分析。

    参数:
        track: 赛道关键词
        account_info: {"account_name": str, "fans_count": int, "positioning": str}
        notes: 结构化笔记列表(来自Agent 0的输出)

    返回:
        {"computed_stats": {...}, "llm_analysis": {...}}
    """
    fans_count = account_info.get("fans_count", 0) or 0

    # 1) 代码计算统计数据(包含互动率)
    computed_stats = _compute_account_stats(notes, fans_count)

    # 2) 采样笔记发送给LLM(使用 MAX_ACCOUNT_NOTES_FOR_LLM 控制token预算)
    sampled = _sample_notes_for_llm(notes, MAX_ACCOUNT_NOTES_FOR_LLM)

    # 格式化输入信息
    account_info_text = (
        f"账号名称: {account_info.get('account_name', '未知')}\n"
        f"粉丝数: {fans_count}\n"
        f"定位: {account_info.get('positioning', '未说明')}"
    )

    computed_stats_text = json.dumps(computed_stats, ensure_ascii=False, indent=2)

    notes_sample_text = json.dumps(
        [
            {
                "title": n.get("title", ""),
                "body_text": (n.get("body_text", "") or "")[:300],
                "hashtags": n.get("hashtags", []),
                "likes": n.get("likes"),
                "comments": n.get("comments"),
                "collects": n.get("collects"),
                "shares": n.get("shares"),
                "post_date": n.get("post_date"),
                "note_type": n.get("note_type"),
            }
            for n in sampled
        ],
        ensure_ascii=False,
        indent=2,
    )

    user_prompt = render(
        account_analysis_prompt.USER_PROMPT_TEMPLATE,
        track=track or "未指定",
        account_info=account_info_text,
        computed_stats=computed_stats_text,
        notes_sample=notes_sample_text,
    )

    # 3) 调用LLM
    llm_analysis = call_llm_json(
        system_prompt=account_analysis_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["account_analyzer"],
        max_tokens=3000,
    )

    if not isinstance(llm_analysis, dict):
        raise ValueError("LLM返回格式异常,预期为JSON对象")

    return {
        "computed_stats": computed_stats,
        "llm_analysis": llm_analysis,
    }
