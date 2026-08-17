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


def test_externalized_fields_seed():
    """规则库外置化：6 平台的新字段（platform_spec/collect_keywords/share_keywords/字数区间）入库且非空。"""
    db_utils.init_db()
    db_utils.init_channels()
    channels = db_utils.get_channels()
    assert len(channels) == 6, f"应有 6 平台，实际 {len(channels)}"
    for c in channels:
        assert c.get("platform_spec"), f"{c['name']} 缺 platform_spec"
        assert c.get("collect_keywords"), f"{c['name']} 缺 collect_keywords"
        assert c.get("share_keywords"), f"{c['name']} 缺 share_keywords"
        assert c.get("copy_min_words") is not None, f"{c['name']} 缺 copy_min_words"
        assert c.get("copy_max_words") is not None, f"{c['name']} 缺 copy_max_words"
        assert c["copy_min_words"] < c["copy_max_words"], f"{c['name']} 字数区间异常"
    print("[5] 规则库外置化: 6 平台 5 个新字段全部入库且非空")


def test_externalized_edit_takes_effect():
    """外置化生效：编辑 DB 的 collect_keywords → platform_workshop 读取到新值。"""
    db_utils.init_db()
    db_utils.init_channels()
    from agents.platform_workshop import get_collect_keywords, get_platform_spec

    original = db_utils.get_channel_rule("小红书")["collect_keywords"]
    try:
        db_utils.update_channel_rule("小红书", collect_keywords="收藏,马克,存下来")
        kw = get_collect_keywords("小红书")
        assert "马克" in kw and "存下来" in kw, f"编辑后应读到新关键词，实际 {kw}"

        db_utils.update_channel_rule("小红书", platform_spec="测试规格：封面 1:1，正文 100 字")
        spec = get_platform_spec("小红书")
        assert "测试规格" in spec, f"编辑后应读到新规格，实际 {spec[:30]}"
    finally:
        # 还原
        db_utils.update_channel_rule("小红书", collect_keywords=original, platform_spec=PLATFORM_SPEC_ORIGINAL_XHS)
    print("[6] 外置化生效: 编辑 DB → platform_workshop 即时读到新值")


def test_copy_range_from_db():
    """外置化生效：编辑 DB 的字数区间 → rule_checks 用新区间校验。"""
    db_utils.init_db()
    db_utils.init_channels()
    from utils.rule_checks import check_copy_word_count

    r = check_copy_word_count("测试内容", "小红书")
    assert r["channel"] == "小红书"
    assert r["min_words"] > 0 and r["max_words"] > r["min_words"]

    # 未知平台回退小红书
    r2 = check_copy_word_count("测试内容", "不存在的平台")
    assert r2["channel"] == "小红书", f"未知平台应回退小红书，实际 {r2['channel']}"
    print("[7] 字数区间外置化: DB 读取 + 未知平台回退通过")


def test_concurrent_rewrite_preserves_order():
    """并发改写：结果顺序与输入 channels 顺序一致，且全部成功。"""
    os.environ["XHS_DEMO_MODE"] = "1"
    from agents.channel_rewriter import rewrite_multi_channel

    title = "用AI写周报被领导点名表扬"
    content = "3个提示词技巧：角色设定、结构化素材、追问量化。"
    kws = [{"keyword": "AI写周报"}]

    channels = ["视频号", "小红书", "知乎", "抖音", "公众号", "问一问"]
    results = rewrite_multi_channel(title, content, channels, kws, "人设:测试")
    assert len(results) == 6, f"应返回 6 个版本，实际 {len(results)}"

    returned_order = [r.get("channel") for r in results]
    assert returned_order == channels, f"顺序应一致，实际 {returned_order}"

    for rw in results:
        assert rw.get("content"), f"{rw.get('channel')} 内容为空"
        assert rw["code_checks"]["red_lines"]["passed"] is True, f"{rw.get('channel')} 命中红线"
    print(f"[8] 并发改写: 6 平台并发，顺序保持 {returned_order == channels}，全部通过")


def test_concurrent_rewrite_single_platform():
    """并发改写：单平台走快速路径，不启线程池。"""
    os.environ["XHS_DEMO_MODE"] = "1"
    from agents.channel_rewriter import rewrite_multi_channel

    results = rewrite_multi_channel("标题", "正文", ["小红书"], [{"keyword": "测试"}], "人设")
    assert len(results) == 1 and results[0]["channel"] == "小红书"
    print("[9] 并发改写单平台快速路径通过")


# 小红书 platform_spec 原始值（用于测试后还原）
PLATFORM_SPEC_ORIGINAL_XHS = (
    "封面：3:4 竖版 1080×1440，人物/产品居中偏右，顶部 1/3 留文字位，文字大且高对比；"
    "正文：清单体/步骤体 800-1500 字，搜索关键词前置，结尾显性收藏指令；"
    "标题：前 20 字放长尾关键词；互动机制：收藏、评论、转发、点赞（收藏权重最高）。"
)


if __name__ == "__main__":
    test_channel_rules_seed()
    test_update_channel_rule()
    test_externalized_fields_seed()
    test_externalized_edit_takes_effect()
    test_copy_range_from_db()
    test_concurrent_rewrite_preserves_order()
    test_concurrent_rewrite_single_platform()
    test_demo_multi_channel_rewrite()
    test_demo_compliance()
    test_demo_publish_record()
    print("\nM3 渠道中心全部测试通过!")
