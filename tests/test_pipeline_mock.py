"""
离线测试:不依赖真实DashScope API Key,用预设的假数据模拟模型返回,
验证Agent1的确定性打分排序逻辑、Agent3的比例核验逻辑是否正确。

运行方式(在项目根目录下):
python -m tests.test_pipeline_mock
"""
from unittest import mock

from agents import trend_filter, topic_generator
from agents.note_scorer import (
    _compute_weighted_total,
    _assign_grade,
    _rank_improvement_priorities,
    _build_effective_weights,
)


def test_trend_filter_scoring():
    fake_llm_output = [
        {
            "topic_id": "1",
            "title": "热点A_数据完整",
            "scores": {"relevance": 9, "freshness": 7, "engagement": 8, "replicability": 6, "extensibility": 9},
            "scoring_confidence": "高",
            "reason": "测试数据A",
        },
        {
            "topic_id": "2",
            "title": "热点B_理应排第一",
            "scores": {"relevance": 10, "freshness": 7, "engagement": 10, "replicability": 10, "extensibility": 10},
            "scoring_confidence": "高",
            "reason": "测试数据B,各维度都很高",
        },
        {
            "topic_id": "3",
            "title": "热点C_数据缺失",
            "scores": {"relevance": 5, "freshness": None, "engagement": 4, "replicability": None, "extensibility": 5},
            "scoring_confidence": "高",
            "reason": "测试数据C,两个维度缺失",
        },
    ]

    with mock.patch("agents.trend_filter.call_llm_json", return_value=fake_llm_output):
        result = trend_filter.filter_trends("AI工具", structured_trends=[], top_n=10)

    scores = [r["total_score"] for r in result["results"]]
    assert scores == sorted(scores, reverse=True), "排序应该按total_score降序"
    assert result["results"][0]["title"] == "热点B_理应排第一", "总分最高的应该排第一"

    c_item = next(r for r in result["results"] if r["title"] == "热点C_数据缺失")
    assert c_item["scoring_confidence"] == "低", "两个维度缺失应该降级为低置信度,实际是" + c_item["scoring_confidence"]

    print("test_trend_filter_scoring 通过")
    print(f"  排序结果: {[r['title'] for r in result['results']]}")
    print(f"  对应total_score: {scores}")


def test_trend_filter_batch_warning():
    """所有条目分数都很低时,应该触发batch_warning而不是静默凑数。"""
    fake_low_scores = [
        {
            "topic_id": str(i),
            "title": f"低质量热点{i}",
            "scores": {"relevance": 2, "freshness": 2, "engagement": 2, "replicability": 2, "extensibility": 2},
            "scoring_confidence": "高",
            "reason": "测试低分场景",
        }
        for i in range(1, 4)
    ]
    with mock.patch("agents.trend_filter.call_llm_json", return_value=fake_low_scores):
        result = trend_filter.filter_trends("冷门赛道", structured_trends=[], top_n=10)

    assert result["batch_warning"] is not None, "全部低分时应该触发batch_warning"
    print("test_trend_filter_batch_warning 通过")
    print(f"  预警内容: {result['batch_warning']}")


def test_topic_generator_ratio_check():
    """实际比例严重偏离目标比例时,应该生成ratio_warning。"""
    fake_topics = [{"content_format": "图文笔记"} for _ in range(8)] + [
        {"content_format": "视频笔记"} for _ in range(2)
    ]
    with mock.patch("agents.topic_generator.call_llm_json", return_value=fake_topics):
        result = topic_generator.generate_topics(
            track="AI工具",
            persona_description="测试人设",
            viral_analysis_report=[],
            topic_count=10,
            format_ratio={"视频笔记": 0.8, "图文笔记": 0.2},
        )
    assert result["ratio_warning"] is not None, "实际比例和目标比例严重偏离时应该触发预警"
    print("test_topic_generator_ratio_check 通过")
    print(f"  预警内容: {result['ratio_warning']}")


def test_topic_generator_ratio_ok():
    """实际比例符合目标比例时,不应该触发ratio_warning。"""
    fake_topics = [{"content_format": "视频笔记"} for _ in range(8)] + [
        {"content_format": "图文笔记"} for _ in range(2)
    ]
    with mock.patch("agents.topic_generator.call_llm_json", return_value=fake_topics):
        result = topic_generator.generate_topics(
            track="AI工具",
            persona_description="测试人设",
            viral_analysis_report=[],
            topic_count=10,
            format_ratio={"视频笔记": 0.8, "图文笔记": 0.2},
        )
    assert result["ratio_warning"] is None, "实际比例符合目标比例时不应该触发预警"
    print("test_topic_generator_ratio_ok 通过")


def test_note_scorer_weighted_total():
    """加权总分计算：正常情况 + 缺失维度时权重自动重分配。"""
    weights = {
        "title_attractiveness": 0.2, "cover_appeal": 0.15, "copy_quality": 0.2,
        "hashtag_strategy": 0.1, "structure_flow": 0.15, "emotion_hook": 0.1,
        "interaction_design": 0.1,
    }
    scores = {
        "title_attractiveness": 10, "cover_appeal": 10, "copy_quality": 10,
        "hashtag_strategy": 10, "structure_flow": 10, "emotion_hook": 10,
        "interaction_design": 10,
    }
    assert _compute_weighted_total(scores, weights) == 50.0, "全满分应是50分"

    # 缺失一个维度时,总分按剩余维度加权计算,不应系统性偏低
    partial = dict(scores)
    partial["cover_appeal"] = None
    total = _compute_weighted_total(partial, weights)
    assert total == 50.0, "缺失维度重分配后满分仍是50,实际" + str(total)

    empty = {k: None for k in weights}
    assert _compute_weighted_total(empty, weights) == 0.0
    print("test_note_scorer_weighted_total 通过")


def test_note_scorer_grade_thresholds():
    """等级判定边界：>=45为S,>=40为A,>=35为B,>=25为C,否则D。"""
    thresholds = [(45, "S"), (40, "A"), (35, "B"), (25, "C"), (0, "D")]
    assert _assign_grade(45, thresholds) == "S"
    assert _assign_grade(44.9, thresholds) == "A"
    assert _assign_grade(40, thresholds) == "A"
    assert _assign_grade(35, thresholds) == "B"
    assert _assign_grade(25, thresholds) == "C"
    assert _assign_grade(24, thresholds) == "D"
    print("test_note_scorer_grade_thresholds 通过")


def test_note_scorer_improvement_priorities():
    """改进优先级应返回分数最低的3个维度,并跳过None。"""
    scores = {
        "title_attractiveness": 9, "cover_appeal": 3, "copy_quality": 5,
        "hashtag_strategy": None, "structure_flow": 7, "emotion_hook": 4,
        "interaction_design": 8,
    }
    priorities = _rank_improvement_priorities(scores)
    assert len(priorities) == 3
    assert priorities == ["cover_appeal", "emotion_hook", "copy_quality"], str(priorities)
    print("test_note_scorer_improvement_priorities 通过")


def test_note_scorer_effective_weights():
    """无封面描述时,cover_appeal权重应按比例分给其余维度。"""
    full = _build_effective_weights(has_cover=True)
    assert abs(sum(full.values()) - 1.0) < 1e-9
    assert "cover_appeal" in full

    no_cover = _build_effective_weights(has_cover=False)
    assert "cover_appeal" not in no_cover
    assert abs(sum(no_cover.values()) - 1.0) < 1e-9, "权重重分配后总和应为1"
    print("test_note_scorer_effective_weights 通过")


if __name__ == "__main__":
    test_trend_filter_scoring()
    test_trend_filter_batch_warning()
    test_topic_generator_ratio_check()
    test_topic_generator_ratio_ok()
    test_note_scorer_weighted_total()
    test_note_scorer_grade_thresholds()
    test_note_scorer_improvement_priorities()
    test_note_scorer_effective_weights()
    print("\n全部离线测试通过!")
