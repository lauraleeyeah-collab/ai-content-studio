"""
M4 数据中心测试：归因确定性计算 + Demo 端到端。

运行方式(在项目根目录下):
python -m tests.test_factory_m4
"""
import os

from agents.attribution_analyzer import compute_attribution, _normalize, _safe_div


def test_normalize():
    """min-max 归一化：边界 0-100、全同值给 50。"""
    assert _normalize([0, 50, 100]) == [0.0, 50.0, 100.0]
    assert _normalize([5, 5, 5]) == [50.0, 50.0, 50.0]
    assert _normalize([]) == []
    print("test_normalize 通过")


def test_safe_div():
    assert _safe_div(10, 0) == 0.0
    assert _safe_div(10, 40) == 0.25
    print("test_safe_div 通过")


def test_attribution_ranking():
    """归因排序：收藏率高的渠道应综合分更高；图文渠道完播率不参与。"""
    metrics = [
        {"channel": "小红书", "views": 1000, "likes": 50, "collects": 120, "comments": 20, "shares": 10,
         "completion_rate": 0.0},
        {"channel": "抖音", "views": 1000, "likes": 200, "collects": 60, "comments": 40, "shares": 5,
         "completion_rate": 0.4},
        {"channel": "视频号", "views": 1000, "likes": 30, "collects": 10, "comments": 5, "shares": 2,
         "completion_rate": 0.2},
    ]
    r = compute_attribution(metrics)
    assert r["best_channel"] == "小红书", f"小红书收藏率最高应第一,实际{r['best_channel']}"
    assert r["worst_channel"] == "视频号", r["worst_channel"]
    assert r["video_channel_count"] == 2, "抖音/视频号算视频渠道"
    # 图文渠道完播率应为 None（不适用）
    xhs = next(c for c in r["channels"] if c["channel"] == "小红书")
    assert xhs["completion_rate_norm"] is None, "图文渠道完播率维度应为None"
    # 视频渠道有完播率归一化
    dy = next(c for c in r["channels"] if c["channel"] == "抖音")
    assert dy["completion_rate_norm"] is not None
    # 综合分排序
    scores = [c["composite"] for c in r["channels"]]
    assert scores == sorted(scores, reverse=True), "综合分应降序"
    print("test_attribution_ranking 通过")


def test_attribution_no_weakness():
    """最佳渠道所有维度并列最高时，最弱维度应为 None（无明显短板）。"""
    metrics = [
        {"channel": "A", "views": 100, "likes": 10, "collects": 20, "comments": 5, "shares": 2, "completion_rate": 0.0},
        {"channel": "B", "views": 100, "likes": 5, "collects": 3, "comments": 1, "shares": 0, "completion_rate": 0.0},
    ]
    r = compute_attribution(metrics)
    assert r["best_channel"] == "A"
    assert r["weakest_dimension"] is None, f"单渠道优势明显时不应有误导性最弱维度:{r['weakest_dimension']}"
    print("test_attribution_no_weakness 通过")


def test_channel_summary_sql():
    """渠道汇总 SQL：回填后能聚合出正确的收藏率/互动率。"""
    from database import db_utils
    db_utils.init_db()
    # 写入一条已知数据（清理旧数据避免干扰）
    with db_utils.get_connection() as conn:
        conn.execute("DELETE FROM platform_metrics")
    db_utils.save_platform_metric(
        publish_record_id=0, channel="测试渠道", content_title="归因测试",
        views=1000, likes=100, collects=200, comments=50, shares=50,
        play_rate=0.0, completion_rate=0.0, collected_at="2026-08-12",
    )
    summary = db_utils.get_channel_summary()
    row = next(s for s in summary if s["channel"] == "测试渠道")
    assert row["total_views"] == 1000
    assert row["total_collects"] == 200
    assert row["collect_rate"] == 0.2, f"收藏率应为0.2,实际{row['collect_rate']}"
    assert row["interaction_rate"] == 0.4, f"互动率应为0.4,实际{row['interaction_rate']}"
    with db_utils.get_connection() as conn:
        conn.execute("DELETE FROM platform_metrics")
    print("test_channel_summary_sql 通过")


def test_demo_attribution():
    """演示模式爆款归因：代码计算 + LLM 解读全流程。"""
    os.environ["XHS_DEMO_MODE"] = "1"
    from utils.demo_data import DEMO_METRICS
    from agents.attribution_analyzer import analyze_attribution

    result = analyze_attribution("AI工具/自我提升", DEMO_METRICS, "用AI写周报系列")
    computed = result["computed"]
    assert computed["sample_count"] == len(DEMO_METRICS)
    assert computed["best_channel"], "应计算出最佳渠道"
    interp = result["interpretation"]
    assert interp and interp.get("recommendations"), "LLM 应给出下一轮生产建议"
    assert interp.get("confidence") in ("high", "medium", "low"), "应给出置信度"
    print(f"[Demo] 爆款归因: best={computed['best_channel']}, 建议数={len(interp.get('recommendations', []))} 通过")


if __name__ == "__main__":
    test_normalize()
    test_safe_div()
    test_attribution_ranking()
    test_attribution_no_weakness()
    test_channel_summary_sql()
    test_demo_attribution()
    print("\nM4 数据中心全部测试通过!")
