"""
标签推荐Agent：根据笔记内容推荐最优标签组合。

模型负责推荐标签和策略说明，代码负责校验标签分布合理性（大词/中词/小词比例）
并按相关性排序，确保推荐结果的可操作性。
"""

from prompts import hashtag_prompt
from utils.llm_client import call_llm_json
from utils.prompt_utils import render
from config import TEMPERATURE_CONFIG


def _validate_mix(recommended: list) -> str | None:
    """
    检查标签的大词/中词/小词分布是否合理。

    如果某一类别占比超过70%，返回警告信息；否则返回None。
    """
    if not recommended:
        return None

    category_counts = {"大词": 0, "中词": 0, "小词": 0}
    for tag_info in recommended:
        category = tag_info.get("category", "")
        if category in category_counts:
            category_counts[category] += 1

    total = len(recommended)
    for category, count in category_counts.items():
        ratio = count / total
        if ratio > 0.7:
            return (
                f'⚠ 标签分布不均："{category}"类标签占比 {ratio:.0%}（{count}/{total}），'
                f"建议增加其他类型的标签以获得更好的流量覆盖。"
            )

    return None


def _sort_by_relevance(recommended: list) -> list:
    """按 relevance_score 降序排列标签列表。"""
    return sorted(
        recommended,
        key=lambda x: x.get("relevance_score", 0),
        reverse=True,
    )


def recommend_hashtags(
    track: str,
    note_title: str,
    note_body: str,
    note_type: str,
    existing_hashtags: str | None = None,
    count: int = 8,
) -> dict:
    """
    为笔记推荐最优标签组合。

    参数:
        track: 赛道关键词
        note_title: 笔记标题
        note_body: 笔记正文（或摘要）
        note_type: 笔记类型（图文/视频）
        existing_hashtags: 用户已有的标签，逗号分隔
        count: 推荐标签数量

    返回: {
        "recommended_hashtags": [...],
        "strategy_note": str,
        "avoid_tags": [...],
        "mix_warning": str | None  # 代码后处理新增
    }
    """
    user_prompt = render(
        hashtag_prompt.USER_PROMPT_TEMPLATE,
        track=track or "未指定",
        note_title=note_title,
        note_body=note_body or "未提供正文内容",
        note_type=note_type or "未指定",
        existing_hashtags=existing_hashtags or "无",
        count=str(count),
    )

    result = call_llm_json(
        system_prompt=hashtag_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["hashtag_recommender"],
    )

    if not isinstance(result, dict):
        raise ValueError("标签推荐返回结果格式异常，预期是对象")

    # 代码后处理：校验分布 + 按相关性排序
    recommended = result.get("recommended_hashtags", [])
    if recommended:
        recommended = _sort_by_relevance(recommended)
        result["recommended_hashtags"] = recommended
        result["mix_warning"] = _validate_mix(recommended)
    else:
        result["mix_warning"] = None

    return result
