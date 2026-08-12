"""
内容报告测试：一键串联 M1-M3 全流程 + 报告完整性。

运行方式(在项目根目录下):
python -m tests.test_factory_report
"""
import os

os.environ["XHS_DEMO_MODE"] = "1"

from utils.demo_data import DEMO_TOPIC


def test_report_full_pipeline():
    """Demo 模式：一个选题 → 完整生产报告，各环节产出齐全。"""
    from agents.content_report_builder import build_content_report

    report = build_content_report(
        "AI工具/自我提升", DEMO_TOPIC["title"], DEMO_TOPIC["angle"], DEMO_TOPIC["content"],
        "人设:深圳搞钱女孩,职场AI提效方向", channels=["小红书", "抖音", "视频号"],
    )

    # M1：搜索词/标题/封面/正文/互动
    assert len(report["search_keywords"]) >= 5
    assert len(report["titles"]) >= 5
    assert any(t.get("keyword_check", {}).get("passed") for t in report["titles"]), "至少1个标题通过关键词检查"
    assert report["cover"]["completeness"]["passed"] is True
    assert report["copy"].get("content"), "正文为空"
    assert report["interaction"].get("collect_reasons"), "互动话术为空"

    # M2：分镜 + 播放优化
    tl = report["script"]["checks"]["timeline"]
    assert tl["passed"] is True, str(tl["issues"])
    assert report["script"]["checks"]["closing_cta"]["present"] is True
    assert report["play"]["checks"]["collect_cta"]["passed"] is True

    # M3：渠道版本 + 合规
    assert len(report["channel_versions"]) == 3
    assert [v["channel"] for v in report["channel_versions"]] == ["小红书", "抖音", "视频号"]
    for ch, comp in report["compliance"].items():
        assert comp["red_lines"]["passed"] is True, f"{ch} 命中红线"
        assert comp["ai_label"].get("template"), f"{ch} 缺AI标注模板"

    print("[1] 全流程产出完整：搜索词/标题/封面/正文/互动/分镜/播放/渠道/合规 全部通过")


def test_report_markdown():
    """报告 Markdown：包含全部 10 个章节与关键内容。"""
    from agents.content_report_builder import build_content_report

    report = build_content_report(
        "AI工具/自我提升", DEMO_TOPIC["title"], DEMO_TOPIC["angle"], DEMO_TOPIC["content"],
        "人设:深圳搞钱女孩,职场AI提效方向", channels=["小红书", "抖音", "视频号"],
    )
    md = report["report_markdown"]
    for section in ["# 内容生产报告", "## 一、搜索词策略", "## 二、标题方案",
                    "## 三、封面提示词", "## 四、图文正文", "## 五、互动话术",
                    "## 六、视频分镜", "## 七、播放优化", "## 八、多平台改写版本",
                    "## 九、合规与 AI 标注", "## 十、发布建议"]:
        assert section in md, f"报告缺少章节: {section}"
    assert "建议收藏" in md or "收藏" in md, "报告应包含收藏指令相关内容"
    print("[2] 报告 Markdown 章节完整（10 章）")


def test_report_channel_validation():
    """渠道参数校验：非法渠道应报错。"""
    from agents.content_report_builder import build_content_report
    try:
        build_content_report("赛道", "标题", "角度", "素材", "人设", channels=["不存在的平台"])
        assert False, "非法渠道应抛错"
    except ValueError:
        pass
    print("[3] 渠道参数校验通过")


if __name__ == "__main__":
    test_report_full_pipeline()
    test_report_markdown()
    test_report_channel_validation()
    print("\n内容报告全部测试通过!")
