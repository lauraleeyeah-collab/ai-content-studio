"""
平台工作台测试：3 平台端到端 + 确定性兜底检查 + 平台参数校验。

运行方式(在项目根目录下):
python -m tests.test_factory_platform
"""
import os

os.environ["XHS_DEMO_MODE"] = "1"

from agents.platform_workshop import produce_for_platform, PLATFORMS, PLATFORM_SPECS


def test_all_platforms_end_to_end():
    """公众号/知乎/小红书 3 平台端到端：产出完整、检查全过。"""

    topic = {"title": "用AI写周报被领导点名表扬", "angle": "真实使用记录", "content": "3个AI写周报提示词技巧"}
    for p in PLATFORMS:
        r = produce_for_platform(
            p, "AI工具/自我提升", topic["title"], topic["angle"], topic["content"], "人设:深圳搞钱女孩",
        )
        assert r["platform"] == p
        assert len(r["titles"]) == 5, f"{p} 标题应5个"
        assert len(r["topic_angles"]) == 3, f"{p} 选题角度应3个"
        assert len(r["search_keywords"]) >= 1
        assert r["copy"].get("content"), f"{p} 正文为空"
        assert r["cover"].get("subject") and r["cover"].get("spec_note")
        assert r["interaction"].get("collect_reasons") and r["interaction"].get("comment_guides")
        ck = r["checks"]
        assert ck["interaction"]["collect_cta"]["passed"], f"{p} 缺收藏引导"
        assert ck["interaction"]["share_cta"]["passed"], f"{p} 缺分享/转发引导"
        assert ck["interaction"]["comment_guides"]["passed"], f"{p} 评论区引导不足"
        assert "平台生产报告" in r["platform_markdown"]
        print(f"[{p}] 端到端通过：5标题/3角度/收藏分享评论检查全过")


def test_platform_validation():
    """非法平台名应报错。"""
    try:
        produce_for_platform("抖音", "赛道", "标题", "", "", "")
        raise AssertionError("应拒绝未接入平台")
    except ValueError as e:
        assert "抖音" in str(e)


def test_platform_specs_complete():
    """3 平台规格齐备：封面/正文/标题/互动机制都有。"""
    assert set(PLATFORMS) == {"小红书", "公众号", "知乎"}
    for p in PLATFORMS:
        spec = PLATFORM_SPECS[p]
        assert "封面" in spec and "正文" in spec and "标题" in spec and "互动" in spec
    print("3 平台规格完整")


def test_platform_specs_demo_data_complete():
    """Demo 数据完整性：每平台标题/封面/正文/互动/角度齐全。"""
    from utils.demo_data import DEMO_PLATFORM_WORKSHOP
    for p in PLATFORMS:
        d = DEMO_PLATFORM_WORKSHOP[p]
        assert len(d["titles"]) == 5
        assert d["cover"]["subject"] and d["cover"]["spec_note"]
        assert d["copy"]["content"] and d["copy"]["structure_note"]
        assert len(d["interaction"]["collect_reasons"]) >= 2
        assert len(d["interaction"]["comment_guides"]) >= 2
        assert len(d["interaction"]["share_guides"]) >= 1
        assert len(d["topic_angles"]) == 3
    print("3 平台 Demo 数据完整")


if __name__ == "__main__":
    test_platform_specs_complete()
    test_platform_specs_demo_data_complete()
    test_platform_validation()
    test_all_platforms_end_to_end()
    print("\n平台工作台全部测试通过!")
