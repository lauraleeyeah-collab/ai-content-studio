"""
互动话术 Agent（M1 图文工厂）。

LLM 生成收藏理由/评论区引导/行动指令，Python 负责：
- 收藏指令显性检查（抖音权重第一是收藏率，指令必须显性出现）
- 行动指令数量下限校验
"""
from prompts import interaction_copywriter_prompt
from utils.llm_client import call_llm_json
from utils.prompt_utils import render
from config import TEMPERATURE_CONFIG

# 显性收藏指令的常见表述（判断兜底，不依赖模型）
COLLECT_CTA_KEYWORDS = ["建议收藏", "先收藏", "记得收藏", "收藏起来", "收藏本文", "收藏这份"]


def _check_collect_cta(collect_reasons: list, cta_suggestions: list) -> dict:
    """检查输出中是否包含显性收藏指令。"""
    all_text = " ".join((collect_reasons or []) + (cta_suggestions or []))
    hit = next((k for k in COLLECT_CTA_KEYWORDS if k in all_text), "")
    return {
        "passed": bool(hit),
        "matched": hit,
        "suggestion": "未检测到显性收藏指令（如「建议收藏」），抖音等平台要求行动指令显性化。" if not hit else "",
    }


def generate_interaction_copy(
    track: str,
    topic_title: str,
    channel: str,
    content: str,
) -> dict:
    """
    生成互动话术方案。

    返回：
    {
        collect_reasons, comment_guides, cta_suggestions, strategy_note,
        checks: {collect_cta}
    }
    """
    user_prompt = render(
        interaction_copywriter_prompt.USER_PROMPT_TEMPLATE,
        track=track or "未指定",
        topic_title=topic_title,
        channel=channel,
        content=content or "（无正文）",
    )

    result = call_llm_json(
        system_prompt=interaction_copywriter_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["interaction_copywriter"],
    )

    if not isinstance(result, dict):
        raise ValueError("互动话术返回结果格式异常，预期是对象")

    result["checks"] = {
        "collect_cta": _check_collect_cta(result.get("collect_reasons"), result.get("cta_suggestions"))
    }
    return result
