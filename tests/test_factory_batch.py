"""
批量生产测试：选题解析 + Demo 批量端到端 + 容错。

运行方式(在项目根目录下):
python -m tests.test_factory_batch
"""
import os

os.environ["XHS_DEMO_MODE"] = "1"

from agents.batch_production import parse_bulk_topics


def test_parse_bulk_topics():
    """多行选题解析：单行/序号/管道/逗号分隔。"""
    raw = """1. 选题一
2. 选题二｜角度二
选题三|角度三|素材三
选题四,角度四,素材四

5、选题五
"""
    topics = parse_bulk_topics(raw)
    assert len(topics) == 5, f"应解析5条,实际{len(topics)}"
    assert topics[0]["title"] == "选题一" and topics[0]["angle"] == "", str(topics[0])
    assert topics[1]["title"] == "选题二" and topics[1]["angle"] == "角度二"
    assert topics[2]["title"] == "选题三" and topics[2]["content"] == "素材三"
    assert topics[3]["title"] == "选题四" and topics[3]["angle"] == "角度四" and topics[3]["content"] == "素材四"
    assert topics[4]["title"] == "选题五", str(topics[4])
    assert parse_bulk_topics("") == []
    assert parse_bulk_topics("  \n\n") == []
    print("test_parse_bulk_topics 通过")


def test_batch_produce_demo():
    """Demo 模式批量生产：3 选题全流程，汇总与合并报告完整。"""
    from agents.batch_production import batch_produce

    topics = [
        {"title": "用AI写周报被领导点名表扬，我的3个提示词技巧", "angle": "真实记录", "content": "3个AI写周报提示词技巧"},
        {"title": "DeepSeek+Excel，1分钟搞定月度数据汇总", "angle": "实操教程", "content": "DeepSeek辅助数据分析流程"},
        {"title": "普通人和高薪的差距，就差这套AI工作流", "angle": "对比视角", "content": "AI工作流提效组合"},
    ]
    progress_ticks = []

    def _cb(done, total, title):
        progress_ticks.append((done, total))

    result = batch_produce(
        topics, "AI工具/自我提升", "人设:深圳搞钱女孩",
        channels=["小红书", "抖音", "视频号"], progress_callback=_cb,
    )

    summary = result["summary"]
    assert summary["total"] == 3
    assert summary["success"] == 3, f"应3条成功,实际{summary['success']}"
    assert summary["failed"] == 0
    assert summary["total_channel_versions"] == 9, f"3选题×3渠道=9,实际{summary['total_channel_versions']}"
    assert len(progress_ticks) == 3, "进度回调应调用3次"

    assert len(result["results"]) == 3
    for r in result["results"]:
        assert r["status"] == "success"
        assert r["report"]["report_markdown"]

    md = result["combined_markdown"]
    assert "批量内容生产报告" in md
    assert "选题 1" in md and "选题 3" in md
    assert md.count("## 选题") == 3
    print("[1] 批量生产：3 选题全部成功，9 渠道版本，合并报告完整")


def test_batch_failure_isolated():
    """容错：空标题选题失败不影响其他选题。"""
    from agents.batch_production import batch_produce

    topics = [
        {"title": "", "angle": "", "content": ""},  # 空标题应失败
        {"title": "正常选题", "angle": "角度", "content": "素材"},
    ]
    result = batch_produce(topics, "赛道", "人设", channels=["小红书", "抖音", "视频号"])
    summary = result["summary"]
    assert summary["failed"] == 1, f"空标题应失败,实际{summary['failed']}"
    assert summary["success"] == 1
    failed = next(r for r in result["results"] if r["status"] == "failed")
    assert failed["error"], "失败应带错误信息"
    ok = next(r for r in result["results"] if r["status"] == "success")
    assert ok["topic_title"] == "正常选题"
    print("[2] 容错：空标题失败不影响正常选题")


if __name__ == "__main__":
    test_parse_bulk_topics()
    test_batch_produce_demo()
    test_batch_failure_isolated()
    print("\n批量生产全部测试通过!")
