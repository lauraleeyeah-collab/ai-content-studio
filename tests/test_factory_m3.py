"""
M3 渠道中心测试：规则库 + 渠道改写 + 合规检查。

运行方式(在项目根目录下):
python -m tests.test_factory_m3
"""
import os
import json

from database import db_utils


def test_channel_rules_seed():
    """规则库初始化：幂等、6 平台、字段齐全。"""
    db_utils.init_db()
    n1 = db_utils.init_channels()
    n2 = db_utils.init_channels()
    assert n1 in (0, 6), f"首次应插入6条(已初始化则0),实际{n1}"
    assert n2 == 0, f"重复初始化应跳过,实际{n2}"

    channels = db_utils.get_channels()
    names = sorted(c["name"] for c in channels)
    assert names == sorted(["小红书", "抖音", "视频号", "公众号", "知乎", "问一问"]), str(names)

    for c in channels:
        assert c.get("algorithm_weights"), f"{c['name']} 缺算法权重"
        assert c.get("red_lines"), f"{c['name']} 缺红线"

    xhs = db_utils.get_channel_rule("小红书")
    assert xhs and "点击率" in xhs["algorithm_weights"]
    print("test_channel_rules_seed 通过")


def test_update_channel_rule():
    """规则卡可编辑更新。"""
    db_utils.init_db()
    db_utils.init_channels()
    db_utils.update_channel_rule("问一问", best_practices="测试更新：答案结构清晰可直接收藏")
    rule = db_utils.get_channel_rule("问一问")
    assert rule["best_practices"].startswith("测试更新"), rule["best_practices"]
    # 还原
    db_utils.update_channel_rule("问一问", best_practices="答案结构清晰可直接收藏；图文并茂；靠广告曝光分成变现；冷启动渠道")
    print("test_update_channel_rule 通过")


def test_demo_multi_channel_rewrite():
    """演示模式一键多平台改写：≥3 平台版本、含改写理由、红线通过。"""
    os.environ["XHS_DEMO_MODE"] = "1"
    from agents.channel_rewriter import rewrite_multi_channel, rewrite_one_channel

    title = "用AI写周报被领导点名表扬，我的3个提示词技巧"
    content = "用AI写周报半年，从被领导说'像流水账'到被评为'重点周报'。3个提示词技巧：给AI角色设定、喂结构化素材、追加追问让进度量化。"
    kws = [{"keyword": "AI写周报"}, {"keyword": "AI提效工具"}]

    channels = ["小红书", "抖音", "视频号"]
    results = rewrite_multi_channel(title, content, channels, kws, "人设:深圳搞钱女孩")
    assert len(results) == 3, f"应返回3个平台版本,实际{len(results)}"
    for rw in results:
        assert rw.get("channel") in channels
        assert rw.get("content"), f"{rw['channel']} 版本内容为空"
        assert rw.get("rewrite_reasons"), f"{rw['channel']} 缺少改写理由"
        assert rw["code_checks"]["red_lines"]["passed"] is True, f"{rw['channel']} 命中红线"
        if rw["channel"] == "抖音":
            assert rw["code_checks"]["has_collect_cta"] is True, "抖音版本应含显性收藏指令"
    print(f"[1] 一键多平台改写: {len(results)} 个版本, 红线/收藏指令/改写理由全部通过")

    # 单平台改写（知乎）也应通过
    zhihu = rewrite_one_channel(title, content, "知乎", kws, "人设:深圳搞钱女孩")
    assert zhihu["channel"] == "知乎" and zhihu["content"]
    print("[2] 单平台改写: 知乎 通过")


def test_demo_compliance():
    """演示模式合规检查：双层检查通过 + AI 标注建议。"""
    os.environ["XHS_DEMO_MODE"] = "1"
    from agents.compliance_checker import check_compliance

    content = "被领导点名表扬的周报，我只改了3个提示词技巧。建议收藏，下次写周报直接翻出来用。"
    result = check_compliance(content, "小红书", red_lines="站外导流、极限词、刷量、搬运", ai_label_required=True)

    assert result["code_checks"]["red_lines"]["passed"] is True
    assert result["llm"]["overall_verdict"] == "pass"
    assert result["passed"] is True
    assert result["ai_label"]["required"] is True
    assert "AI" in result["ai_label"]["template"]
    print("[3] 合规检查: 双层检查通过, AI 标注模板就绪")


def test_demo_publish_record():
    """发布记录落库与状态更新（M4 回填的基础）。"""
    db_utils.init_db()
    rid = db_utils.save_publish_record(
        asset_id=0, channel="小红书", final_title="测试发布",
        final_content="测试内容", checklist_json=json.dumps({"ai_label": "ok"}),
        publish_time="2026-08-13 20:00", status="ready",
    )
    assert rid > 0
    db_utils.update_publish_record(rid, status="published")
    records = db_utils.get_publish_records(limit=5)
    assert any(r["id"] == rid and r["status"] == "published" for r in records)
    # 清理测试记录
    with db_utils.get_connection() as conn:
        conn.execute("DELETE FROM publish_records WHERE id = ?", (rid,))
    print("[4] 发布记录: 落库与状态更新通过")


if __name__ == "__main__":
    test_channel_rules_seed()
    test_update_channel_rule()
    test_demo_multi_channel_rewrite()
    test_demo_compliance()
    test_demo_publish_record()
    print("\nM3 渠道中心全部测试通过!")
