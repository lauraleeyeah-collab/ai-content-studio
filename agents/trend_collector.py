"""
Agent 0: 热点采集/结构化Agent
负责把用户粘贴的原始文本,调用模型解析成结构化的热点列表。
"""
from prompts import collector_prompt
from utils.llm_client import call_llm_json
from utils.prompt_utils import render
from config import TEMPERATURE_CONFIG


def collect_trends(track: str, raw_text_blob: str) -> list:
    """
    输入用户粘贴的原始文本块,返回结构化热点列表(list of dict)。
    """
    user_prompt = render(
        collector_prompt.USER_PROMPT_TEMPLATE,
        track=track or "未指定",
        raw_text_blob=raw_text_blob,
    )
    result = call_llm_json(
        system_prompt=collector_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["collector"],
    )
    if not isinstance(result, list):
        raise ValueError("Agent0返回结果格式异常,预期是数组")
    return result
