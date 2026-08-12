"""
Agent 3: 选题生成Agent

模型负责选题创意、借鉴溯源和去重判断,但内容形式比例(视频/图文)是否
严重偏离目标比例,由这里的Python代码统计模型实际输出的分布后确定性
判断,生成ratio_warning,不完全依赖模型自觉遵守比例要求。
"""
import json

from prompts import topic_prompt
from utils.llm_client import call_llm_json
from utils.prompt_utils import render
from config import TEMPERATURE_CONFIG, DEFAULT_TOPIC_COUNT, DEFAULT_FORMAT_RATIO

# 实际比例与目标比例的偏离超过这个阈值就触发预警
RATIO_DEVIATION_THRESHOLD = 0.3


def generate_topics(
    track: str,
    persona_description: str,
    viral_analysis_report: list,
    history_topics: list = None,
    topic_count: int = None,
    format_ratio: dict = None,
) -> dict:
    """
    返回 {"ratio_warning": ..., "topics": [...]}
    """
    topic_count = topic_count or DEFAULT_TOPIC_COUNT
    format_ratio = format_ratio or DEFAULT_FORMAT_RATIO
    history_topics = history_topics or []

    user_prompt = render(
        topic_prompt.USER_PROMPT_TEMPLATE,
        track=track or "未指定",
        persona_description=persona_description,
        viral_analysis_report=json.dumps(viral_analysis_report, ensure_ascii=False),
        history_topics=json.dumps(history_topics, ensure_ascii=False),
        topic_count=str(topic_count),
        format_ratio=json.dumps(format_ratio, ensure_ascii=False),
    )
    topics = call_llm_json(
        system_prompt=topic_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["topic_generator"],
    )
    if not isinstance(topics, list):
        raise ValueError("Agent3返回结果格式异常,预期是数组")

    ratio_warning = _check_format_ratio(topics, format_ratio)
    return {"ratio_warning": ratio_warning, "topics": topics}


def _check_format_ratio(topics: list, format_ratio: dict) -> str:
    """
    统计topics里content_format的实际分布,和目标比例做对比,
    偏离超过RATIO_DEVIATION_THRESHOLD就生成预警文案,否则返回None。
    """
    if not topics:
        return None

    total = len(topics)
    actual_counts = {}
    for t in topics:
        fmt = t.get("content_format", "未知")
        actual_counts[fmt] = actual_counts.get(fmt, 0) + 1

    deviations = []
    for fmt, target_ratio in format_ratio.items():
        actual_ratio = actual_counts.get(fmt, 0) / total
        if abs(actual_ratio - target_ratio) > RATIO_DEVIATION_THRESHOLD:
            deviations.append(f"{fmt}目标比例{target_ratio:.0%},实际{actual_ratio:.0%}")

    if deviations:
        return "内容形式分配偏离默认比例较多:" + ";".join(deviations)
    return None
