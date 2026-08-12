"""
Agent 2: 爆款分析Agent
主要是定性拆解,这里的代码只负责调用模型、解析JSON并做基本格式校验,
不对内容做二次计算。
"""
import json

from prompts import analysis_prompt
from utils.llm_client import call_llm_json
from utils.prompt_utils import render
from config import TEMPERATURE_CONFIG


def analyze_viral_notes(track: str, selected_trends: list) -> list:
    """
    输入精选热点列表(完整字段,非仅topic_id),返回每条的爆款拆解结果。
    """
    user_prompt = render(
        analysis_prompt.USER_PROMPT_TEMPLATE,
        track=track or "未指定",
        selected_trends=json.dumps(selected_trends, ensure_ascii=False),
    )
    result = call_llm_json(
        system_prompt=analysis_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["analyzer"],
    )
    if not isinstance(result, list):
        raise ValueError("Agent2返回结果格式异常,预期是数组")
    return result
