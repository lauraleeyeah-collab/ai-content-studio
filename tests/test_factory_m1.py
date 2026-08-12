"""
M1 图文工厂测试：确定性规则 + Agent 后处理 + Demo 端到端。

运行方式(在项目根目录下):
python -m tests.test_factory_m1
"""
import os

from utils.rule_checks import (
    check_title_keywords,
    check_copy_word_count,
    scan_red_lines,
    check_cover_prompt_completeness,
)
from agents.search_keyword_analyzer import _post_process
from agents.interaction_copywriter import _check_collect_cta


# ══════════════ 确定性规则 ══════════════

def test_title_keyword_check():
    """标题前 20 字关键词检查：命中/未命中/空输入。"""
    r = check_title_keywords("AI写周报的3个技巧，领导追着我要模板", ["AI写周报", "周报模板"])
    assert r["passed"] is True, "核心关键词在前20字内应通过"
    assert "AI写周报" in r["matched_in_prefix"]

    r2 = check_title_keywords("领导追着我要模板，这3个技巧绝了", ["AI写周报"])
    assert r2["passed"] is False, "关键词不在前20字应不通过"
    assert r2["suggestion"], "应给出改写建议"

    r3 = check_title_keywords("", ["AI写周报"])
    assert r3["passed"] is False, "空标题不应通过"

    r4 = check_title_keywords("随便一个标题", [])
    assert r4["passed"] is True, "无关键词时不应误报"
    print("test_title_keyword_check 通过")


def test_copy_word_count():
    """正文字数区间校验：过短/正常/过长。"""
    short = check_copy_word_count("太短了", "小红书")
    assert short["status"] == "too_short", short["status"]

    ok = check_copy_word_count("干货" * 100, "小红书")
    assert ok["status"] == "ok", ok["status"]

    long = check_copy_word_count("水" * 4000, "问一问")
    assert long["status"] == "too_long", long["status"]

    unknown = check_copy_word_count("内容" * 50, "不存在的平台")
    assert unknown["channel"] == "小红书", "未知平台应回退到小红书区间"
    print("test_copy_word_count 通过")


def test_red_lines():
    """红线词硬校验：极限词/导流词命中，正常文案通过。"""
    hit = scan_red_lines("全网第一的AI工具，加微信领取教程")
    assert hit["passed"] is False
    categories = {h["category"] for h in hit["hits"]}
    assert "极限词" in categories and "站外导流" in categories, str(categories)

    ok = scan_red_lines("分享3个AI工具的使用技巧，建议收藏备用。")
    assert ok["passed"] is True
    print("test_red_lines 通过")


def test_cover_completeness():
    """封面提示词完整性校验。"""
    full = check_cover_prompt_completeness({
        "subject": "主体", "style": "风格", "composition": "构图", "text_slot": "文字"
    })
    assert full["passed"] is True

    missing = check_cover_prompt_completeness({"subject": "主体", "style": "风格"})
    assert missing["passed"] is False
    assert set(missing["missing"]) == {"composition", "text_slot"}
    print("test_cover_completeness 通过")


# ══════════════ Agent 后处理 ══════════════

def test_keyword_post_process():
    """搜索词后处理：按优先级排序、同词去重、长度过滤。"""
    raw = [
        {"keyword": "低优先级词", "priority": 3, "search_intent": "找答案"},
        {"keyword": "高优先级词", "priority": 9, "search_intent": "找教程"},
        {"keyword": "高优先级词", "priority": 7, "search_intent": "重复出现但分低"},
        {"keyword": "中优先级词", "priority": 5, "search_intent": "找清单", "is_long_tail": True},
        {"keyword": "X", "priority": 10, "search_intent": "太短应过滤"},
        {"keyword": "这是一个超过二十个字符的超级长的关键词应该被过滤掉", "priority": 10, "search_intent": "太长应过滤"},
        {"keyword": "", "priority": 10, "search_intent": "空词应过滤"},
        "非字典条目应过滤",
    ]
    result = _post_process(raw)
    assert [k["keyword"] for k in result] == ["高优先级词", "中优先级词", "低优先级词"], str(result)
    assert result[0]["priority"] == 9, "同词去重应保留更高优先级"
    assert len(result) == 3
    print("test_keyword_post_process 通过")


def test_collect_cta_check():
    """收藏指令显性检查。"""
    ok = _check_collect_cta(["建议收藏，下次直接用"], ["收藏本文"])
    assert ok["passed"] is True

    bad = _check_collect_cta(["这篇很有用"], ["点个赞吧"])
    assert bad["passed"] is False
    assert bad["suggestion"], "未通过时应给建议"
    print("test_collect_cta_check 通过")


# ══════════════ Demo 端到端 ══════════════

def test_demo_factory_pipeline():
    """演示模式跑通 M1 图文工厂全流程。"""
    os.environ["XHS_DEMO_MODE"] = "1"
    from utils.demo_data import DEMO_TOPIC
    from agents.search_keyword_analyzer import analyze_search_keywords
    from agents.title_optimizer import generate_title_variants
    from agents.cover_prompt_generator import generate_cover_prompt
    from agents.platform_copywriter import rewrite_for_channel, SUPPORTED_CHANNELS
    from agents.interaction_copywriter import generate_interaction_copy

    track = "AI工具/自我提升"
    persona = "人设:深圳搞钱女孩,职场AI提效方向"

    # 搜索词
    kws = analyze_search_keywords(track, DEMO_TOPIC["title"], DEMO_TOPIC["angle"], persona)
    assert isinstance(kws, list) and len(kws) >= 5, f"搜索词应≥5个,实际{len(kws)}"
    assert kws[0]["priority"] >= kws[-1]["priority"], "应按优先级降序"
    print(f"[1] 搜索词分析: {len(kws)} 个, Top1={kws[0]['keyword']} 通过")

    # 标题 + 关键词检查
    variants = generate_title_variants(track, DEMO_TOPIC["title"], DEMO_TOPIC["angle"], persona, 5)
    kw_list = [k["keyword"] for k in kws]
    passed_titles = [v for v in variants if check_title_keywords(v.get("title", ""), kw_list)["passed"]]
    assert len(passed_titles) >= 1, "至少应有1个标题通过关键词位置检查"
    print(f"[2] 标题生成: {len(variants)} 个, {len(passed_titles)} 个通过关键词前20字检查")

    # 封面提示词
    cover = generate_cover_prompt(track, DEMO_TOPIC["title"], "小红书", "图文笔记",
                                  "、".join(k["keyword"] for k in kws[:3]))
    assert cover.get("completeness", {}).get("passed") is True, "封面提示词应完整"
    assert cover.get("text_slot"), "应包含文字位"
    print("[3] 封面提示词: 完整性校验通过")

    # 平台改写（4 个图文平台）
    for channel in SUPPORTED_CHANNELS:
        rewritten = rewrite_for_channel(track, DEMO_TOPIC["title"], channel, DEMO_TOPIC["content"],
                                        kws, persona)
        assert rewritten.get("content"), f"{channel} 版正文为空"
        wc = rewritten["checks"]["word_count"]
        assert wc["status"] in ("ok", "too_short", "too_long"), f"{channel} 字数校验异常"
        assert rewritten["checks"]["red_lines"]["passed"] is True, f"{channel} 版命中红线"
        print(f"[4] 平台改写: {channel} 通过（{wc['chars']}字）")

    # 互动话术
    interaction = generate_interaction_copy(track, DEMO_TOPIC["title"], "小红书", rewritten["content"])
    assert interaction.get("collect_reasons"), "应包含收藏理由"
    assert interaction["checks"]["collect_cta"]["passed"] is True, "应包含显性收藏指令"
    print("[5] 互动话术: 收藏指令检查通过")


if __name__ == "__main__":
    test_title_keyword_check()
    test_copy_word_count()
    test_red_lines()
    test_cover_completeness()
    test_keyword_post_process()
    test_collect_cta_check()
    test_demo_factory_pipeline()
    print("\nM1 图文工厂全部测试通过!")
