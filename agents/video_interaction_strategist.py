"""
视频互动策略 Agent（M2 视频工厂）。

LLM 生成置顶评论/引导问题/分享理由，Python 负责红线词复核。
"""
from prompts import video_interaction_prompt
from utils.llm_client import call_llm_json
from utils.prompt_utils import render
from utils.rule_checks import scan_red_lines
from config import TEMPERATURE_CONFIG


def generate_video_interaction(
    track: str,
    topic_title: str,
    channel: str,
    script_summary: str,
) -> dict:
    """
    生成视频互动策略，附加红线复核：
    {comment_pin, engagement_questions, share_reasons, reply_strategy, risk_notes, checks}
    """
    user_prompt = render(
        video_interaction_prompt.USER_PROMPT_TEMPLATE,
        track=track or "未指定",
        topic_title=topic_title,
        channel=channel,
        script_summary=script_summary or "（无脚本摘要）",
    )

    result = call_llm_json(
        system_prompt=video_interaction_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["video_interaction"],
        max_tokens=1500,
    )

    if not isinstance(result, dict):
        raise ValueError("视频互动策略返回结果格式异常，预期是对象")

    all_text = " ".join(
        (result.get("engagement_questions") or []) + (result.get("share_reasons") or [])
        + [result.get("comment_pin", ""), result.get("reply_strategy", "")]
    )
    result["checks"] = {"red_lines": scan_red_lines(all_text)}
    return result
