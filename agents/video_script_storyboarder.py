"""
视频分镜脚本 Agent（M2 视频工厂）。

LLM 生成秒级分镜，Python 负责确定性校验：
- 时间轴连续性（无重叠、无空隙、从 0 开始）
- 总时长匹配目标模板（±2 秒）
- 每个镜头必填字段检查（visual/voiceover/subtitle）
"""
from prompts import video_script_prompt
from utils.llm_client import call_llm_json
from utils.prompt_utils import render
from config import TEMPERATURE_CONFIG

DURATION_TEMPLATES = video_script_prompt.DURATION_TEMPLATES
TOLERANCE_SECONDS = 2


def _validate_storyboard(storyboard: list, target_seconds: int) -> dict:
    """时间轴与字段校验，返回 {passed, issues, total_seconds}。"""
    issues = []
    if not storyboard:
        return {"passed": False, "issues": ["分镜为空"], "total_seconds": 0}

    prev_end = 0
    for idx, shot in enumerate(storyboard):
        try:
            start = int(shot.get("time_start", -1))
            end = int(shot.get("time_end", -1))
        except (TypeError, ValueError):
            issues.append(f"镜头{idx + 1} 时间不是数字")
            continue

        if start != prev_end:
            issues.append(f"镜头{idx + 1} 时间轴不连续（期望从{prev_end}开始，实际{start}）")
        if end <= start:
            issues.append(f"镜头{idx + 1} 时长非法（{start}→{end}）")
        for field in ("visual", "voiceover", "subtitle"):
            if not (shot.get(field) or "").strip():
                issues.append(f"镜头{idx + 1} 缺少字段：{field}")
        prev_end = end

    total = prev_end
    if abs(total - target_seconds) > TOLERANCE_SECONDS:
        issues.append(f"总时长 {total}s 与模板 {target_seconds}s 偏差超过{TOLERANCE_SECONDS}s")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "total_seconds": total,
        "target_seconds": target_seconds,
        "shot_count": len(storyboard),
    }


def generate_video_script(
    track: str,
    topic_title: str,
    topic_angle: str,
    channel: str,
    duration_seconds: int,
    search_keywords: list,
    persona_description: str,
) -> dict:
    """
    生成秒级分镜脚本。

    返回：
    {
        video_title_hook, duration_seconds, storyboard, closing_cta,
        checks: {timeline, red_lines}
    }
    """
    if str(duration_seconds) not in DURATION_TEMPLATES:
        raise ValueError(f"不支持的时长模板：{duration_seconds}，可选 {list(DURATION_TEMPLATES)}")

    kw_text = "、".join(k.get("keyword", "") for k in (search_keywords or [])[:3])
    user_prompt = render(
        video_script_prompt.USER_PROMPT_TEMPLATE,
        track=track or "未指定",
        topic_title=topic_title,
        topic_angle=topic_angle or "未提供",
        channel=channel,
        duration_seconds=str(duration_seconds),
        search_keywords=kw_text or "无",
        persona_description=persona_description or "未提供",
    )

    result = call_llm_json(
        system_prompt=video_script_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["video_storyboarder"],
        max_tokens=3000,
    )

    if not isinstance(result, dict) or not result.get("storyboard"):
        raise ValueError("分镜脚本返回结果格式异常，缺少 storyboard")

    storyboard = result.get("storyboard", [])
    result["checks"] = {
        "timeline": _validate_storyboard(storyboard, int(duration_seconds)),
        "closing_cta": {
            "text": result.get("closing_cta", ""),
            "present": any(k in (result.get("closing_cta", "") or "") for k in ("建议收藏", "先收藏", "收藏起来")),
        },
    }
    return result
