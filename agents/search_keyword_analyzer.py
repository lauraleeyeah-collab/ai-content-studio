"""
搜索词分析 Agent（M1 图文工厂）。

LLM 负责拆解用户会搜索的关键词，Python 负责：
- 按 priority 降序排序
- 去重（同词不同意图时保留最高优先级）
- 长度与合法性过滤
- 长尾词标记
"""
from prompts import search_keyword_prompt
from utils.llm_client import call_llm_json
from utils.prompt_utils import render
from config import TEMPERATURE_CONFIG

MAX_KEYWORDS = 10
MIN_KEYWORD_LEN = 2
MAX_KEYWORD_LEN = 20


def _post_process(raw_keywords: list) -> list:
    """确定性处理：过滤非法词、去重、按优先级排序。"""
    seen = {}
    for item in raw_keywords or []:
        if not isinstance(item, dict):
            continue
        keyword = (item.get("keyword") or "").strip()
        if not (MIN_KEYWORD_LEN <= len(keyword) <= MAX_KEYWORD_LEN):
            continue
        priority = item.get("priority")
        if not isinstance(priority, (int, float)) or not (1 <= priority <= 10):
            priority = 5
        # 同词去重：保留优先级更高的那条
        if keyword not in seen or priority > seen[keyword]["priority"]:
            seen[keyword] = {
                "keyword": keyword,
                "search_intent": item.get("search_intent", "找答案"),
                "priority": int(priority),
                "is_long_tail": bool(item.get("is_long_tail", False)),
            }

    result = sorted(seen.values(), key=lambda x: -x["priority"])
    return result[:MAX_KEYWORDS]


def analyze_search_keywords(
    track: str,
    topic_title: str,
    topic_angle: str,
    persona_description: str,
) -> list:
    """
    生成搜索词清单，返回按 priority 降序的关键词列表：
    [{keyword, search_intent, priority, is_long_tail}, ...]
    """
    user_prompt = render(
        search_keyword_prompt.USER_PROMPT_TEMPLATE,
        track=track or "未指定",
        topic_title=topic_title,
        topic_angle=topic_angle or "未提供",
        persona_description=persona_description or "未提供",
    )

    raw = call_llm_json(
        system_prompt=search_keyword_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["search_keyword_analyzer"],
    )

    if not isinstance(raw, list):
        raise ValueError("搜索词分析返回结果格式异常，预期是数组")

    return _post_process(raw)


def top_keyword_list(keywords: list, count: int = 3) -> list:
    """取优先级最高的前 N 个关键词（供标题关键词检查使用）。"""
    return [k["keyword"] for k in (keywords or [])][:count]
