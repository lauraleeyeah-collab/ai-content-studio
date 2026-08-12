"""
爆款归因 Agent（M4 数据中心）。

代码负责确定性计算：指标归一化（0-100）、渠道对比、维度强弱排序；
LLM 只负责解读归因结果，避免模型对数字的不可靠判断。
"""
from prompts import attribution_prompt
from utils.llm_client import call_llm_json
from utils.prompt_utils import render
from config import TEMPERATURE_CONFIG


def _safe_div(a, b):
    return round(a / b, 3) if b else 0.0


def _normalize(values: list) -> list:
    """min-max 归一化到 0-100；全 0 或单值时给默认 50。"""
    if not values:
        return []
    vmax = max(values)
    vmin = min(values)
    if vmax == vmin:
        return [50.0] * len(values)
    return [round((v - vmin) / (vmax - vmin) * 100, 1) for v in values]


def compute_attribution(metrics: list) -> dict:
    """
    确定性归因计算（不调用模型）。

    输入 metrics: [{"channel": "小红书", "views": 1000, "collects": 120, "comments": 30, "completion_rate": 0.35, ...}]
    输出：
    {
        channels: [{channel, collect_rate, interaction_rate, completion_norm, collect_norm, ...}],
        best_channel, worst_channel, weakest_dimension, sample_count
    }
    """
    if not metrics:
        return {"channels": [], "best_channel": None, "worst_channel": None,
                "weakest_dimension": None, "sample_count": 0}

    channels = []
    for m in metrics:
        views = m.get("views") or 0
        collects = m.get("collects") or 0
        likes = m.get("likes") or 0
        comments = m.get("comments") or 0
        shares = m.get("shares") or 0
        interactions = likes + collects + comments + shares
        channels.append({
            "channel": m.get("channel", "未知"),
            "views": views,
            "collect_rate": _safe_div(collects, views),
            "interaction_rate": _safe_div(interactions, views),
            "completion_rate": m.get("completion_rate") or 0.0,
            "play_rate": m.get("play_rate") or 0.0,
        })

    # 完播率维度只对视频向渠道适用（有 play/completion 数据的），图文渠道标记为不适用
    video_channels = [c for c in channels if c["completion_rate"] > 0 or c["play_rate"] > 0]

    # 各维度归一化：收藏率/互动率对全部渠道；完播率只对视频渠道
    for dim, key in (("收藏率", "collect_rate"), ("互动率", "interaction_rate")):
        norm = _normalize([c[key] for c in channels])
        for c, v in zip(channels, norm):
            c[f"{key}_norm"] = v
    for dim, key in (("完播率", "completion_rate"),):
        norm = _normalize([c[key] for c in video_channels])
        for c, v in zip(video_channels, norm):
            c[f"{key}_norm"] = v
        for c in channels:
            if c not in video_channels:
                c[f"{key}_norm"] = None  # 图文渠道：维度不适用

    # 综合分 = 可用维度的加权平均（收藏率权重最高，符合平台趋势）
    for c in channels:
        weights = {"collect_rate_norm": 0.5, "interaction_rate_norm": 0.3, "completion_rate_norm": 0.2}
        total_w = 0.0
        acc = 0.0
        for key, w in weights.items():
            v = c.get(key)
            if v is not None:
                acc += v * w
                total_w += w
        c["composite"] = round(acc / total_w, 1) if total_w else 0.0

    channels.sort(key=lambda x: -x["composite"])
    best = channels[0]["channel"]
    worst = channels[-1]["channel"]

    # 最弱维度：对最佳渠道而言，可用（非 None）维度中归一化分最低的
    best_norms = {}
    for label, key in (("收藏率", "collect_rate_norm"), ("互动率", "interaction_rate_norm"),
                       ("完播率", "completion_rate_norm")):
        v = channels[0].get(key)
        if v is not None:
            best_norms[label] = v
    # 所有可用维度归一化分相同（无短板）时返回 None，避免误导性归因
    weakest_dimension = None
    if best_norms and len(set(best_norms.values())) > 1:
        weakest_dimension = min(best_norms, key=best_norms.get)

    return {
        "channels": channels,
        "best_channel": best,
        "worst_channel": worst,
        "weakest_dimension": weakest_dimension,
        "video_channel_count": len(video_channels),
        "sample_count": len(metrics),
    }


def analyze_attribution(track: str, metrics: list, topic_context: str = "") -> dict:
    """
    爆款归因：代码计算 + LLM 解读。

    返回：
    {
        computed: compute_attribution 的确定性结果,
        interpretation: LLM 归因解读
    }
    """
    computed = compute_attribution(metrics)
    if not computed["channels"]:
        return {"computed": computed, "interpretation": None}

    user_prompt = render(
        attribution_prompt.USER_PROMPT_TEMPLATE,
        track=track or "未指定",
        topic_context=topic_context or "未提供",
        attribution_data=__import__("json").dumps(computed, ensure_ascii=False),
    )

    interpretation = call_llm_json(
        system_prompt=attribution_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["attribution_analyzer"],
        max_tokens=1200,
    )

    return {"computed": computed, "interpretation": interpretation}
