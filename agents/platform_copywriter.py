"""
平台化正文改写 Agent（M1 图文工厂）。

LLM 按平台规则改写正文，Python 负责：
- 字数区间校验（PLATFORM_COPY_RANGES）
- 红线词扫描（基础词表）
- 搜索词覆盖检查
"""
from prompts import platform_copywriter_prompt
from utils.llm_client import call_llm_json
from utils.prompt_utils import render
from utils.rule_checks import check_copy_word_count, scan_red_lines
from config import TEMPERATURE_CONFIG

SUPPORTED_CHANNELS = ["小红书", "公众号", "知乎", "问一问"]


def _join_keywords(keywords: list) -> str:
    if not keywords:
        return "无"
    if isinstance(keywords[0], dict):
        return "、".join(k.get("keyword", "") for k in keywords)
    return "、".join(str(k) for k in keywords)


def rewrite_for_channel(
    track: str,
    topic_title: str,
    channel: str,
    source_content: str,
    search_keywords: list,
    persona_description: str,
) -> dict:
    """
    把素材正文改写为目标平台版本。

    返回：
    {
        content, structure_note, rewrite_reasons,
        checks: {word_count, red_lines, keyword_coverage}
    }
    """
    if channel not in SUPPORTED_CHANNELS:
        raise ValueError(f"暂不支持该平台改写：{channel}，可选 {SUPPORTED_CHANNELS}")

    user_prompt = render(
        platform_copywriter_prompt.USER_PROMPT_TEMPLATE,
        track=track or "未指定",
        topic_title=topic_title,
        channel=channel,
        search_keywords=_join_keywords(search_keywords),
        persona_description=persona_description or "未提供",
        source_content=source_content or "（无素材正文，请根据标题与搜索词自行展开）",
    )

    result = call_llm_json(
        system_prompt=platform_copywriter_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["platform_copywriter"],
    )

    if not isinstance(result, dict) or not result.get("content"):
        raise ValueError("平台改写返回结果格式异常，缺少 content 字段")

    content = result["content"].strip()

    result["checks"] = {
        "word_count": check_copy_word_count(content, channel),
        "red_lines": scan_red_lines(content),
        "keyword_coverage": {
            "present": [k.get("keyword") for k in search_keywords[:3] if isinstance(k, dict) and k.get("keyword") in content],
            "missing": [k.get("keyword") for k in search_keywords[:3] if isinstance(k, dict) and k.get("keyword") not in content],
        },
    }
    return result
