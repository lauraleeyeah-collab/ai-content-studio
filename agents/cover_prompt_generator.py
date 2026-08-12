"""
封面提示词 Agent（M1 图文工厂）。

LLM 生成 AI 生图提示词（主体/风格/构图/文字位/配色），
Python 负责完整性校验（check_cover_prompt_completeness），
保证产出可被生图工具直接使用。
"""
from prompts import cover_prompt_prompt
from utils.llm_client import call_llm_json
from utils.prompt_utils import render
from utils.rule_checks import check_cover_prompt_completeness
from config import TEMPERATURE_CONFIG


def generate_cover_prompt(
    track: str,
    topic_title: str,
    channel: str,
    content_format: str,
    search_keywords: str,
) -> dict:
    """
    生成封面提示词，返回 dict，附加 completeness 校验结果：
    {subject, style, composition, text_slot, color_scheme, negative_hint, completeness}
    """
    user_prompt = render(
        cover_prompt_prompt.USER_PROMPT_TEMPLATE,
        track=track or "未指定",
        topic_title=topic_title,
        channel=channel,
        content_format=content_format or "图文笔记",
        search_keywords=search_keywords or "无",
    )

    result = call_llm_json(
        system_prompt=cover_prompt_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["cover_prompt_generator"],
    )

    if not isinstance(result, dict):
        raise ValueError("封面提示词返回结果格式异常，预期是对象")

    result["completeness"] = check_cover_prompt_completeness(result)
    return result
