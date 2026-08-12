"""
视频播放优化 Agent（M2 视频工厂）。

LLM 给出钩子/收藏/完播建议，Python 负责确定性检查：
- collect_cta 是否显性含收藏指令（抖音收藏率第一权重）
- five_sec_hook 是否非空且长度合理
"""
from prompts import video_play_prompt
from utils.llm_client import call_llm_json
from utils.prompt_utils import render
from config import TEMPERATURE_CONFIG

COLLECT_CTA_KEYWORDS = ["建议收藏", "先收藏", "记得收藏", "收藏起来", "收藏本文", "收藏这份"]


def _check_collect_cta(text: str) -> dict:
    hit = next((k for k in COLLECT_CTA_KEYWORDS if k and k in (text or "")), "")
    return {
        "passed": bool(hit),
        "matched": hit,
        "suggestion": "未检测到显性收藏指令（如「建议收藏」），抖音权重第一是收藏率，指令必须显性。" if not hit else "",
    }


def _check_hook(hook: str) -> dict:
    hook = (hook or "").strip()
    return {
        "passed": bool(hook) and 5 <= len(hook) <= 60,
        "chars": len(hook),
        "suggestion": "前 5 秒钩子为空或过长，建议控制在 5-60 字内的强结果承诺。" if not (bool(hook) and 5 <= len(hook) <= 60) else "",
    }


def optimize_video_play(
    track: str,
    topic_title: str,
    channel: str,
    duration_seconds: int,
    script_text: str,
) -> dict:
    """
    输出播放优化方案，附加确定性检查：
    {five_sec_hook, hook_assessment, collect_cta, completion_tips, subtitle_tips, risks, checks}
    """
    user_prompt = render(
        video_play_prompt.USER_PROMPT_TEMPLATE,
        track=track or "未指定",
        topic_title=topic_title,
        channel=channel,
        duration_seconds=str(duration_seconds),
        script_text=script_text or "（无脚本）",
    )

    result = call_llm_json(
        system_prompt=video_play_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["video_play_optimizer"],
        max_tokens=2000,
    )

    if not isinstance(result, dict):
        raise ValueError("播放优化返回结果格式异常，预期是对象")

    result["checks"] = {
        "collect_cta": _check_collect_cta(result.get("collect_cta", "")),
        "hook": _check_hook(result.get("five_sec_hook", "")),
    }
    return result
