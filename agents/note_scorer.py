"""
Agent: 笔记爆款分析Agent (Note Scorer)
对单篇小红书笔记进行7维度评分,LLM负责打分和给建议,
代码负责加权计算总分、判定等级、排序改进优先级。
"""
import json

from prompts import note_score_prompt
from utils.llm_client import call_llm_json
from utils.prompt_utils import render
from config import TEMPERATURE_CONFIG, NOTE_SCORE_WEIGHTS, GRADE_THRESHOLDS


# 全部7个维度key,顺序与Prompt中一致
ALL_DIMENSIONS = [
    "title_attractiveness",
    "cover_appeal",
    "copy_quality",
    "hashtag_strategy",
    "structure_flow",
    "emotion_hook",
    "interaction_design",
]


def _compute_weighted_total(scores: dict, weights: dict) -> float:
    """
    加权平均后归一化到50分制。
    自动跳过分数为None的维度,将其权重按比例分配给其他维度。
    """
    active_dims = {k: v for k, v in scores.items() if v is not None and k in weights}
    if not active_dims:
        return 0.0

    active_weight_sum = sum(weights[k] for k in active_dims)
    if active_weight_sum == 0:
        return 0.0

    weighted_sum = 0.0
    for k, v in active_dims.items():
        normalized_weight = weights[k] / active_weight_sum
        weighted_sum += v * normalized_weight * 5  # *5 将1-10分映射到0-50分制

    return round(weighted_sum, 1)


def _assign_grade(total_score: float, thresholds: list) -> str:
    """
    根据总分和阈值列表判定等级。
    thresholds: [(分数下限, 等级), ...] 从高到低排列
    """
    for threshold, grade in thresholds:
        if total_score >= threshold:
            return grade
    return thresholds[-1][1]


def _rank_improvement_priorities(scores: dict) -> list:
    """
    按分数从低到高排序,返回分数最低的3个维度key作为改进优先级。
    自动跳过None值。
    """
    valid = [(k, v) for k, v in scores.items() if v is not None]
    valid.sort(key=lambda x: x[1])
    return [k for k, _ in valid[:3]]


def _build_effective_weights(has_cover: bool) -> dict:
    """
    根据是否有封面描述,计算实际生效的权重分配。
    如果缺少封面描述,将 cover_appeal 的权重(0.15)按比例分配给其余6个维度。
    """
    if has_cover:
        return dict(NOTE_SCORE_WEIGHTS)

    # 去掉 cover_appeal,将其权重按比例分给其他维度
    cover_weight = NOTE_SCORE_WEIGHTS.get("cover_appeal", 0.15)
    other_weights = {k: v for k, v in NOTE_SCORE_WEIGHTS.items() if k != "cover_appeal"}
    other_total = sum(other_weights.values())
    if other_total == 0:
        # 极端防御:其他权重全为0,退化为均分
        n = len(other_weights)
        return {k: 1.0 / n for k in other_weights}

    effective = {}
    for k, w in other_weights.items():
        effective[k] = w + cover_weight * (w / other_total)
    return effective


def score_single_note(track: str, note_data: dict, persona_description: str = None) -> dict:
    """
    对单篇笔记进行完整评分,返回包含各维度分数、总分、等级和改进优先级的结果字典。

    note_data 字段:
      title, body_text, hashtags, likes, comments, collects, shares,
      note_type, cover_description(可为None)

    返回:
      {
        "dimensions": {key: {"score": N, "reason": "...", "suggestion": "..."}, ...},
        "overall_comment": "...",
        "total_score": float (50分制),
        "grade": "S/A/B/C/D",
        "improvement_priorities": [dim_key, dim_key, dim_key],
        "effective_weights": {key: float, ...},
      }
    """
    persona = persona_description or "未指定"

    # 格式化笔记数据为可读文本
    note_data_str = json.dumps(note_data, ensure_ascii=False, indent=2)

    user_prompt = render(
        note_score_prompt.USER_PROMPT_TEMPLATE,
        track=track or "未指定",
        note_data=note_data_str,
        persona_description=persona,
    )

    llm_result = call_llm_json(
        system_prompt=note_score_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["note_scorer"],
        max_tokens=3000,
    )

    # 提取各维度分数(LLM输出scores字段)
    raw_scores = llm_result.get("scores", llm_result.get("dimensions", {}))

    # 构建标准化的 scores 字典
    dim_scores = {}
    for dim_key in ALL_DIMENSIONS:
        dim_data = raw_scores.get(dim_key, {})
        if isinstance(dim_data, dict):
            dim_scores[dim_key] = {
                "score": dim_data.get("score"),
                "reason": dim_data.get("reason", ""),
                "suggestion": dim_data.get("suggestion", ""),
            }
        else:
            dim_scores[dim_key] = {"score": None, "reason": "", "suggestion": ""}

    # 提取纯分数用于计算
    score_values = {k: v["score"] for k, v in dim_scores.items()}

    # 计算有效权重、加权总分、等级、改进优先级
    effective_weights = _build_effective_weights(bool(note_data.get("cover_description")))
    total_score = _compute_weighted_total(score_values, effective_weights)
    grade = _assign_grade(total_score, GRADE_THRESHOLDS)
    improvement_priorities = _rank_improvement_priorities(score_values)

    return {
        "scores": dim_scores,
        "total_score": total_score,
        "grade": grade,
        "improvement_priorities": improvement_priorities,
        "effective_weights": effective_weights,
    }
