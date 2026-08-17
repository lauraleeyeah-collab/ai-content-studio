"""
标题优化Agent：生成标题变体 + 多维度评分。

生成阶段使用较高temperature保证创意多样性，
评分阶段使用低temperature保证评分一致性。
总分由代码计算（5维度均值 * 2 → 百分制），排名和判定也由代码确定性完成。
"""

from prompts import title_optimizer_prompt
from utils.llm_client import call_llm_json
from utils.prompt_utils import render
from config import TEMPERATURE_CONFIG, TITLE_VERDICT_THRESHOLDS


def generate_title_variants(
    track: str,
    original_title: str,
    topic_context: str,
    persona_description: str,
    variant_count: int = 5,
) -> list:
    """
    根据原始标题和主题背景，生成多个标题变体。

    返回: [{"title": str, "formula_type": str, "rationale": str}, ...]
    """
    user_prompt = render(
        title_optimizer_prompt.GENERATE_USER_PROMPT_TEMPLATE,
        track=track or "未指定",
        original_title=original_title,
        topic_context=topic_context or "无额外背景信息",
        persona_description=persona_description or "未提供",
        variant_count=str(variant_count),
    )

    result = call_llm_json(
        system_prompt=title_optimizer_prompt.GENERATE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["title_generator"],
    )

    if not isinstance(result, list):
        raise ValueError("标题生成返回结果格式异常，预期是数组")

    return result


def _compute_total_score(scores: dict) -> float:
    """
    计算总分：5个维度取均值后 * 2，映射到0-100分制。

    对缺失维度做容错：按实际可用维度数量求均值。
    """
    dimensions = ["click_curiosity", "keyword_relevance", "emotional_resonance",
                  "information_clarity", "uniqueness"]
    available = [scores.get(d) for d in dimensions if scores.get(d) is not None]
    if not available:
        return 0.0
    avg = sum(available) / len(available)
    return round(avg * 2, 1)


def _compute_verdict(total_score: float) -> str:
    """根据总分和阈值配置返回判定结果。"""
    for threshold, verdict in TITLE_VERDICT_THRESHOLDS:
        if total_score >= threshold:
            return verdict
    return "不推荐"


def score_title_variants(
    track: str,
    title_variants: list,
    topic_context: str,
) -> list:
    """
    对标题变体进行多维度评分。

    参数:
        track: 赛道关键词
        title_variants: 标题列表，可以是字符串列表或包含"title"键的字典列表
        topic_context: 主题背景

    返回: [{"title", "scores", "total_score", "rank", "verdict"}, ...]
          按total_score降序排列，rank为1-based排名。
    """
    # 统一提取标题文本
    if title_variants and isinstance(title_variants[0], dict):
        titles_text = "\n".join(
            f"{i+1}. {v['title']}" for i, v in enumerate(title_variants)
        )
    else:
        titles_text = "\n".join(f"{i+1}. {t}" for i, t in enumerate(title_variants))

    user_prompt = render(
        title_optimizer_prompt.SCORE_USER_PROMPT_TEMPLATE,
        track=track or "未指定",
        title_variants=titles_text,
        topic_context=topic_context or "无额外背景信息",
    )

    raw_scores = call_llm_json(
        system_prompt=title_optimizer_prompt.SCORE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["title_scorer"],
    )

    if not isinstance(raw_scores, list):
        raise ValueError("标题评分返回结果格式异常，预期是数组")

    # 代码计算：总分、排名、判定
    for item in raw_scores:
        scores = item.get("scores", {}) or {}
        item["total_score"] = _compute_total_score(scores)

    # 按总分降序排列并赋予排名
    raw_scores.sort(key=lambda x: -x.get("total_score", 0))
    for rank, item in enumerate(raw_scores, start=1):
        item["rank"] = rank
        item["verdict"] = _compute_verdict(item["total_score"])

    return raw_scores
