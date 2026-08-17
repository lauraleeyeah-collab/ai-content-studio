"""
Demo 模式端到端测试：设置 XHS_DEMO_MODE=1 后，所有 LLM 调用返回内置示例数据，
验证完整流程能跑通、确定性后处理逻辑（打分排序/比例核验/等级判定）正常执行。

运行方式(在项目根目录下):
python -m tests.test_demo_mode
"""
import os

os.environ["XHS_DEMO_MODE"] = "1"

from agents.trend_collector import collect_trends
from agents.trend_filter import filter_trends
from agents.viral_analyzer import analyze_viral_notes
from agents.topic_generator import generate_topics
from agents.copywriter import generate_copy
from agents.note_scorer import score_single_note
from agents.title_optimizer import generate_title_variants, score_title_variants
from agents.hashtag_recommender import recommend_hashtags
from agents.trend_summarizer import summarize_trends
from agents.account_analyzer import analyze_account
from agents.image_extractor import extract_from_images
from utils.demo_data import DEMO_RAW_TEXT, DEMO_STRUCTURED

TRACK = "AI工具/自我提升"
PERSONA = (
    "人设:深圳搞钱女孩,定位是借助AI工具辅助工作效率和个人成长,内容覆盖英语学习、阅读、"
    "职场发展、理财、搞钱副业、自律习惯六个方向,内容配比为干货80%+情绪20%。"
)


def test_full_pipeline():
    structured = collect_trends(TRACK, DEMO_RAW_TEXT)
    assert isinstance(structured, list) and len(structured) == 3, "应提取出3条示例笔记"
    assert all(t.get("title") and t.get("likes") is not None for t in structured)
    print(f"[1] 采集结构化: {len(structured)} 条通过")

    filtered = filter_trends(TRACK, structured, top_n=10)
    results = filtered["results"]
    scores = [r["total_score"] for r in results]
    assert scores == sorted(scores, reverse=True), "应按total_score降序排序"
    assert results[0]["title"].startswith("普通人3天"), "最高分应是'副业收益'那条"
    assert filtered.get("batch_warning") is None
    print(f"[2] 热点筛选: 排序正确, 最高分 {results[0]['total_score']} 通过")

    analyzed = analyze_viral_notes(TRACK, structured)
    assert isinstance(analyzed, list) and len(analyzed) == 3
    assert all(a.get("title_formula") and a.get("replicability") for a in analyzed)
    print(f"[3] 爆款拆解: {len(analyzed)} 条通过")

    topics_result = generate_topics(
        TRACK, PERSONA, analyzed,
        history_topics=[], topic_count=10,
        format_ratio={"视频笔记": 0.8, "图文笔记": 0.2},
    )
    topics = topics_result["topics"]
    assert len(topics) == 10, "应生成10个选题"
    assert topics_result["ratio_warning"] is None, "示例数据比例应符合配置"
    video_count = sum(1 for t in topics if t["content_format"] == "视频笔记")
    assert video_count == 8, f"视频笔记应为8条,实际{video_count}"
    assert all(t.get("borrowed_from") and t.get("persona_fit") for t in topics)
    print(f"[4] 选题生成: {len(topics)} 条, 视频{video_count}条, 比例核验通过")

    copy_text = generate_copy(TRACK, PERSONA, topics[0], analyzed[0], "风格说明")
    assert isinstance(copy_text, str) and len(copy_text) > 100, "文案应是非空长文本"
    assert "#AI工具" in copy_text
    print(f"[5] 文案生成: {len(copy_text)} 字通过")


def test_note_scorer():
    result = score_single_note(TRACK, DEMO_STRUCTURED[0], PERSONA)
    assert result["grade"] in ("S", "A", "B", "C", "D")
    assert 0 <= result["total_score"] <= 50
    assert len(result["improvement_priorities"]) == 3
    print(f"[6] 笔记爆款分析: 总分{result['total_score']}, 等级{result['grade']} 通过")


def test_title_and_hashtag():
    variants = generate_title_variants(TRACK, DEMO_STRUCTURED[0]["title"], "AI改简历", PERSONA, variant_count=6)
    assert len(variants) == 6
    scored = score_title_variants(TRACK, variants, "AI改简历")
    assert scored[0]["rank"] == 1
    assert scored[0]["total_score"] >= scored[-1]["total_score"]
    print(f"[7] 标题优化: {len(variants)} 个变体, 评分排序正确 通过")

    ht = recommend_hashtags(TRACK, "用AI改简历", "3步实操", "图文笔记")
    tags = ht["recommended_hashtags"]
    assert len(tags) == 8
    assert ht["mix_warning"] is None, "示例标签分布不应触发警告"
    print(f"[8] 标签推荐: {len(tags)} 个标签, 分布校验通过")


def test_trend_and_account():
    notes = DEMO_STRUCTURED * 3
    trend = summarize_trends(TRACK, notes, "最近7天")
    assert "computed_stats" in trend and "llm_summary" in trend
    assert isinstance(trend["llm_summary"]["dominant_themes"], list)
    print("[9] 趋势分析: 统计+LLM摘要 通过")

    account = analyze_account(
        TRACK,
        {"account_name": "搞钱日记本", "fans_count": 89000, "positioning": "AI副业"},
        notes,
    )
    assert "computed_stats" in account and "llm_analysis" in account
    assert len(account["llm_analysis"]["strengths"]) >= 3
    print("[10] 竞品分析: 统计+LLM分析 通过")


def test_image_extractor():
    """Demo 模式下截图识别返回内置示例结构化笔记。"""
    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=(255, 0, 0)).save(buf, format="PNG")
    notes = extract_from_images(TRACK, [{"bytes": buf.getvalue(), "mime": "image/png"}])
    assert isinstance(notes, list) and len(notes) == 2, "应返回2条示例笔记"
    assert all(n.get("title") and n.get("likes") is not None for n in notes)
    print(f"[11] 截图识别: {len(notes)} 条 通过")


if __name__ == "__main__":
    test_full_pipeline()
    test_note_scorer()
    test_title_and_hashtag()
    test_trend_and_account()
    test_image_extractor()
    print("\nDemo 模式端到端测试全部通过!")
