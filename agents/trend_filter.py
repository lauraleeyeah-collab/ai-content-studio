"""
Agent 1: 热点筛选Agent

模型只负责给出五个维度的主观打分,total_score的加总、归一化、平局排序、
batch_warning的判断,全部由这里的Python代码确定性完成,避免依赖模型自己
做算术和排序——这是本项目里少数"LLM负责判断,代码负责计算"的关键设计点。
"""
import json

from prompts import filter_prompt
from utils.llm_client import call_llm_json
from utils.prompt_utils import render
from config import TEMPERATURE_CONFIG, DEFAULT_TOP_N, LOW_SCORE_THRESHOLD

DIMENSIONS = ["relevance", "freshness", "engagement", "replicability", "extensibility"]


def _compute_total_score(scores: dict) -> tuple:
    """
    返回(total_score, missing_count)。

    可用维度分数求和后,按"可用维度数量"归一化到50分制(5个维度*10分),
    这样不会因为某个维度缺失就让总分系统性偏低,不同条目之间仍然可比。
    missing_count用于决定scoring_confidence要不要降级。
    """
    available = [scores.get(d) for d in DIMENSIONS if scores.get(d) is not None]
    missing_count = len(DIMENSIONS) - len(available)
    if not available:
        return 0.0, missing_count
    total = sum(available) / len(available) * len(DIMENSIONS)
    return round(total, 1), missing_count


def filter_trends(track: str, structured_trends: list, top_n: int = None) -> dict:
    """
    输入结构化热点列表,返回 {"batch_warning": ..., "results": [...]}
    results按total_score降序排列,长度不超过top_n。
    """
    top_n = top_n or DEFAULT_TOP_N

    user_prompt = render(
        filter_prompt.USER_PROMPT_TEMPLATE,
        track=track or "未指定",
        structured_trends=json.dumps(structured_trends, ensure_ascii=False),
    )
    raw_results = call_llm_json(
        system_prompt=filter_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["filter"],
    )
    if not isinstance(raw_results, list):
        raise ValueError("Agent1返回结果格式异常,预期是数组")

    enriched = []
    for item in raw_results:
        scores = item.get("scores", {}) or {}
        total_score, missing_count = _compute_total_score(scores)

        confidence = item.get("scoring_confidence", "高")
        if missing_count >= 2:
            confidence = "低"
        elif missing_count == 1 and confidence == "高":
            confidence = "中"

        enriched.append({**item, "total_score": total_score, "scoring_confidence": confidence})

    def sort_key(x):
        s = x.get("scores", {}) or {}
        # total_score降序为主排序;relevance、engagement依次作为平局判定
        return (-x["total_score"], -(s.get("relevance") or 0), -(s.get("engagement") or 0))

    enriched.sort(key=sort_key)
    results = enriched[:top_n]

    batch_warning = None
    if results and all(r["total_score"] < LOW_SCORE_THRESHOLD for r in results):
        batch_warning = (
            f"本批{len(results)}条热点的total_score均低于{LOW_SCORE_THRESHOLD}分(满分50),"
            "整体质量偏低,建议补充更多样本或放宽相关赛道范围,而不是直接用这批结果继续往下走。"
        )

    return {"batch_warning": batch_warning, "results": results}
