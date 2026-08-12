"""
M2 视频工厂测试：确定性校验 + Demo 端到端。

运行方式(在项目根目录下):
python -m tests.test_factory_m2
"""
import os

from agents.video_script_storyboarder import _validate_storyboard
from agents.video_play_optimizer import _check_collect_cta, _check_hook


def _shots():
    return [
        {"time_start": 0, "time_end": 5, "visual": "近景", "voiceover": "开头", "subtitle": "字幕1"},
        {"time_start": 5, "time_end": 15, "visual": "中景", "voiceover": "中段", "subtitle": "字幕2"},
        {"time_start": 15, "time_end": 30, "visual": "远景", "voiceover": "结尾", "subtitle": "字幕3"},
    ]


# ══════════════ 确定性校验 ══════════════

def test_timeline_valid():
    """时间轴连续且总时长匹配时应通过。"""
    r = _validate_storyboard(_shots(), 30)
    assert r["passed"] is True, str(r["issues"])
    assert r["total_seconds"] == 30
    assert r["shot_count"] == 3
    print("test_timeline_valid 通过")


def test_timeline_gap():
    """时间轴有空隙（不连续）应报错。"""
    shots = _shots()
    shots[1]["time_start"] = 6
    r = _validate_storyboard(shots, 30)
    assert r["passed"] is False
    assert any("不连续" in i for i in r["issues"]), str(r["issues"])
    print("test_timeline_gap 通过")


def test_timeline_duration_mismatch():
    """总时长与模板偏差超过容差应报错。"""
    r = _validate_storyboard(_shots(), 60)
    assert r["passed"] is False
    assert any("偏差" in i for i in r["issues"]), str(r["issues"])
    print("test_timeline_duration_mismatch 通过")


def test_timeline_missing_field():
    """镜头缺画面/口播/字幕字段应报错。"""
    shots = _shots()
    del shots[1]["voiceover"]
    r = _validate_storyboard(shots, 30)
    assert r["passed"] is False
    assert any("缺少字段" in i for i in r["issues"]), str(r["issues"])
    print("test_timeline_missing_field 通过")


def test_play_checks():
    """收藏指令与钩子检查。"""
    ok = _check_collect_cta("建议收藏，下次直接用")
    assert ok["passed"] is True and ok["matched"] == "建议收藏"

    bad = _check_collect_cta("点个赞吧")
    assert bad["passed"] is False and bad["suggestion"]

    h_ok = _check_hook("被领导点名表扬的周报，我只改了3个地方。")
    assert h_ok["passed"] is True

    h_empty = _check_hook("")
    assert h_empty["passed"] is False and h_empty["suggestion"]
    print("test_play_checks 通过")


# ══════════════ Demo 端到端 ══════════════

def test_demo_video_pipeline():
    """演示模式跑通 M2 视频工厂全流程。"""
    os.environ["XHS_DEMO_MODE"] = "1"
    from utils.demo_data import DEMO_TOPIC
    from agents.video_script_storyboarder import generate_video_script
    from agents.video_play_optimizer import optimize_video_play
    from agents.video_interaction_strategist import generate_video_interaction
    from agents.search_keyword_analyzer import analyze_search_keywords
    import json

    track = "AI工具/自我提升"
    persona = "人设:深圳搞钱女孩,职场AI提效方向"
    kws = analyze_search_keywords(track, DEMO_TOPIC["title"], DEMO_TOPIC["angle"], persona)

    script = generate_video_script(track, DEMO_TOPIC["title"], DEMO_TOPIC["angle"], "抖音", 60, kws, persona)
    tl = script["checks"]["timeline"]
    assert tl["passed"] is True, str(tl["issues"])
    assert tl["total_seconds"] == 60, f"总时长应为60s,实际{tl['total_seconds']}"
    assert script["checks"]["closing_cta"]["present"] is True, "结尾应含显性收藏指令"
    print(f"[1] 分镜脚本: {tl['shot_count']} 镜头 / {tl['total_seconds']}s，时间轴与收藏指令通过")

    play = optimize_video_play(track, DEMO_TOPIC["title"], "抖音", 60,
                               json.dumps(script["storyboard"], ensure_ascii=False))
    assert play["checks"]["collect_cta"]["passed"] is True, "播放优化应含显性收藏指令"
    assert play["checks"]["hook"]["passed"] is True, "钩子应非空且长度合理"
    print("[2] 播放优化: 收藏指令与钩子检查通过")

    interaction = generate_video_interaction(track, DEMO_TOPIC["title"], "抖音",
                                             json.dumps(script["storyboard"][:3], ensure_ascii=False))
    assert interaction.get("comment_pin"), "应包含置顶评论"
    assert interaction["checks"]["red_lines"]["passed"] is True, "互动策略不应命中红线"
    print("[3] 互动策略: 置顶评论与红线复核通过")


if __name__ == "__main__":
    test_timeline_valid()
    test_timeline_gap()
    test_timeline_duration_mismatch()
    test_timeline_missing_field()
    test_play_checks()
    test_demo_video_pipeline()
    print("\nM2 视频工厂全部测试通过!")
