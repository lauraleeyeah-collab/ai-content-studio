"""
视频生成提示词 Agent（M2 延伸）。

LLM 把分镜脚本转换为指定模型的生成提示词，Python 负责确定性校验：
- 镜头数一致性（shots 数 == storyboard 镜头数）
- 每个镜头必填字段（prompt / time_range / audio_instruction）
- time_range 与分镜时间轴对应
"""
import json

from prompts.video_gen_prompt import MODEL_CONFIGS, SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from utils.llm_client import call_llm_json
from utils.prompt_utils import render
from config import TEMPERATURE_CONFIG

GENERIC_NEGATIVE = "画面模糊, 人物变形, 多余手指, 文字乱码, 低画质, 闪烁"


def get_model_options() -> list:
    """返回支持的模型列表。"""
    return list(MODEL_CONFIGS.keys())


def _validate(result: dict, storyboard: list) -> dict:
    """确定性校验：镜头数、必填字段、时间轴对应。"""
    issues = []
    shots = result.get("shots") or []
    expected = len(storyboard)

    if len(shots) != expected:
        issues.append(f"镜头数不一致：分镜 {expected} 个，提示词 {len(shots)} 个")

    for idx, shot in enumerate(shots):
        if not (shot.get("prompt") or "").strip():
            issues.append(f"镜头{idx + 1} 缺少 prompt")
        if not (shot.get("time_range") or "").strip():
            issues.append(f"镜头{idx + 1} 缺少 time_range")
        if not (shot.get("audio_instruction") or "").strip():
            issues.append(f"镜头{idx + 1} 缺少 audio_instruction")
        # 时间轴对应（模糊校验：期望起点包含在分镜时间区间附近）
        if idx < expected:
            src = storyboard[idx]
            expected_range = f"{src.get('time_start')}s-{src.get('time_end')}s"
            if shot.get("time_range") != expected_range:
                issues.append(f"镜头{idx + 1} 时间轴不匹配：期望 {expected_range}，实际 {shot.get('time_range')}")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "shot_count": len(shots),
        "expected_shot_count": expected,
    }


def build_video_gen_prompts(
    model: str,
    storyboard: list,
    video_title: str,
    duration_seconds: int,
) -> dict:
    """
    把分镜脚本转换为指定模型的生成提示词（不调用生成 API）。

    返回：
    {
        model, global_style_prompt, shots: [{shot_index, time_range, prompt, negative_prompt, audio_instruction}],
        model_tips, negative_base, checks: {structure}
    }
    """
    if model not in MODEL_CONFIGS:
        raise ValueError(f"不支持的模型：{model}，可选 {get_model_options()}")

    cfg = MODEL_CONFIGS[model]
    user_prompt = render(
        USER_PROMPT_TEMPLATE,
        model=model,
        model_strengths=cfg["strengths"],
        storyboard_json=json.dumps(storyboard, ensure_ascii=False),
        video_title=video_title or "（未命名）",
        duration_seconds=str(duration_seconds),
    )

    result = call_llm_json(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["video_gen_prompt"],
        max_tokens=3000,
    )

    if not isinstance(result, dict):
        raise ValueError("视频生成提示词返回结果格式异常，预期是对象")

    result["negative_base"] = GENERIC_NEGATIVE
    result["model_tips"] = (result.get("model_tips") or []) + cfg["tips"]
    result["checks"] = {"structure": _validate(result, storyboard)}
    return result


def build_prompt_export_markdown(result: dict) -> str:
    """把生成提示词导出为 Markdown（可直接粘贴使用）。"""
    lines = [
        f"# 视频生成提示词（{result.get('model', '')}）",
        "",
        f"**视频：** {result.get('video_title', '') or ''}",
        "",
        "## 全局一致性提示词",
        "",
        result.get("global_style_prompt", ""),
        "",
        f"**通用负向提示词：** {result.get('negative_base', '')}",
        "",
    ]
    for shot in result.get("shots", []):
        lines += [
            f"## 镜头 {shot.get('shot_index')}（{shot.get('time_range')}）",
            "",
            f"**提示词：** {shot.get('prompt', '')}",
            "",
            f"**负向：** {shot.get('negative_prompt', '')}",
            "",
            f"**音画：** {shot.get('audio_instruction', '')}",
            "",
        ]
    lines += ["## 模型使用提示", ""]
    for tip in result.get("model_tips", []):
        lines.append(f"- {tip}")
    return "\n".join(lines)
