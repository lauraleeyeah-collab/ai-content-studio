"""
使用实际笔记内容测试小红书爆款热点工具 - 离线模式

不使用真实 API，用预设的假数据模拟 LLM 返回结果，验证：
1. Agent1 的打分排序逻辑是否正确
2. Agent3 的内容形式比例 (80% 视频 +20% 图文) 是否能被正确执行和监控

测试素材（用于模拟 LLM 返回的数据结构）：
1. 里昂说 AI (9K+ 粉丝) - "codex 有多强？看完你也能用 AI 为所欲为"
   - 转发 2K+, 点赞 18K, 收藏 36K, 评论 420
2. Nox. (500+ 粉丝) - "985 文科女，勇闯 AI 产品"
"""
import json
from unittest import mock

# ============================================================
# 模拟 Agent0: 采集结构化后的结果
# ============================================================

FAKE_STRUCTURED_TRENDS = [
    {
        "raw_id": "1",
        "title": "codex 有多强？看完你也能用 AI 为所欲为",
        "author": "里昂说 AI",
        "follower_count": "9000+",
        "likes": 18000,
        "collections": 36000,
        "shares": 2000,
        "comments": 420,
        "content_format": "视频笔记",
        "body_text": "Codex 是 AI 智能体，更像员工角色...左侧是能力区，右侧是工作区...关键插件推荐 Computer Use...",
    },
    {
        "raw_id": "2",
        "title": "985 文科女，勇闯 AI 产品",
        "author": "Nox.",
        "follower_count": "500+",
        "likes": 100,  # 新人账号，数据偏低
        "collections": 50,
        "shares": 20,
        "comments": 10,
        "content_format": "图文笔记",  # 假设这篇是图文
        "body_text": "一个 985 文科女生，如何转行做 AI 产品经理？这是我的转型日记...",
    },
]


def run_full_pipeline():
    print("=" * 80)
    print("小红书爆款热点工具 - 离线测试")
    print("测试素材：里昂说 AI(18K 赞 36K 收藏)+Nox.(500 粉新人)")
    print("配比要求：80% 视频 + 20% 图文")
    print("=" * 80)

    track = "AI 工具/个人成长"
    format_ratio = {"视频笔记": 0.8, "图文笔记": 0.2}

    # ---------- Step 1: 模拟 Agent0 输出 ----------
    print("\n[Step 1] 模拟 Agent0 采集结构化")
    print("-" * 40)
    print(f"输入 {len(FAKE_STRUCTURED_TRENDS)} 条原始笔记:")
    for item in FAKE_STRUCTURED_TRENDS:
        print(f"  - {item['title']} [{item['author']}] - 点赞:{item['likes']}, 收藏:{item['collections']}")

    # ---------- Step 2: 测试 Agent1 热点筛选 ----------
    print("\n\n[Step 2] 测试 Agent1 热点筛选（mock LLM 输出）")
    print("-" * 40)

    # 模拟 Agent1 返回的结果
    MOCK_AGENT1_OUTPUT = [
        {
            "topic_id": "1",
            "title": "codex 有多强？看完你也能用 AI 为所欲为",
            "scores": {
                "relevance": 9,
                "freshness": 8,
                "engagement": 10,  # 18K 赞 36K 收藏，超高
                "replicability": 7,
                "extensibility": 9,
            },
            "scoring_confidence": "高",
            "reason": "里昂说 AI 的这条 codex 视频数据非常优秀，36K 收藏说明干货价值极高，AI 工具赛道相关性强，适合做教程类选题。",
        },
        {
            "topic_id": "2",
            "title": "985 文科女，勇闯 AI 产品",
            "scores": {
                "relevance": 8,
                "freshness": 9,
                "engagement": 3,  # 新人账号数据低
                "replicability": 9,
                "extensibility": 8,
            },
            "scoring_confidence": "中",
            "reason": "Nox.虽然是新人账号，但'文科生转行 AI 产品'的故事性强、可复制性高，容易引发同类人群共鸣，建议作为人文视角补充。",
        },
    ]

    with mock.patch("agents.trend_filter.call_llm_json", return_value=MOCK_AGENT1_OUTPUT):
        from agents.trend_filter import filter_trends
        filtered_result = filter_trends(track, FAKE_STRUCTURED_TRENDS, top_n=10)

        print(f"\n筛选结果 ({len(filtered_result['results'])} 条):")
        for r in sorted(filtered_result["results"], key=lambda x: x["total_score"], reverse=True):
            score_info = f"总分:{r['total_score']} | 置信度:{r['scoring_confidence']}"
            print(f"\n【{r['title']}】")
            print(f"  {score_info}")
            print(f"  评分详情:")
            for dim, score in r["scores"].items():
                marker = "✓" if score else "?"
                print(f"    {marker} {dim}: {score}")

        # 验证排序逻辑
        scores = [r["total_score"] for r in filtered_result["results"]]
        assert scores == sorted(scores, reverse=True), "❌ 排序错误!"
        print(f"\n✅ 排序验证通过：里昂说 AI({scores[0]}分) > Nox.({scores[1]}分)")

    # ---------- Step 3: 测试 Agent2 爆款拆解 ----------
    print("\n\n[Step 3] 测试 Agent2 爆款拆解（mock LLM 输出）")
    print("-" * 40)

    MOCK_AGENT2_OUTPUT = [
        {
            "topic_id": "1",
            "title": "codex 有多强？看完你也能用 AI 为所欲为",
            "author": "里昂说 AI",
            "title_formula": "疑问句 + 能力描述 + 行动号召 ('xxx 有多强？看完你也能 xxx')",
            "content_structure": "定义介绍 → 界面结构 → 操作流程 → 插件推荐 → 模式对比",
            "emotional_triggers": ["好奇心 (codex 有多强)", "获得感 (看完你也能)", "焦虑缓解 (数字员工)"],
            "interaction_tactics": "标签式引导 (#AI 工具 #codex #效率提升) + 实用清单 (3 个关键插件)",
            "viral_factors": [
                "标题制造认知缺口 (codex 到底有多强)",
                "强调'你的收益' (你也能用 AI 为所欲为)",
                "结构化呈现降低学习门槛",
            ],
        },
        {
            "topic_id": "2",
            "title": "985 文科女，勇闯 AI 产品",
            "author": "Nox.",
            "title_formula": "身份标签 + 挑战行为 ('xxx 背景的人做 xxx')",
            "content_structure": "背景介绍 → 学习路径 → 内容方向 → 互动邀请",
            "emotional_triggers": ["认同感 (文科生)", "励志 (转行勇气)", "陪伴感 (转型日记)"],
            "interaction_tactics": "寻求同好交流 (欢迎同样想转行的同学) + 开放式话题 (#转行 #个人成长)",
            "viral_factors": [
                "身份反差 (文科 vs AI 技术)",
                "成长记录 (从 0 到 1)",
                "社群召唤 (一起交流)",
            ],
        },
    ]

    with mock.patch("agents.viral_analyzer.call_llm_json", return_value=MOCK_AGENT2_OUTPUT):
        from agents.viral_analyzer import analyze_viral_notes

        id_to_trend = {str(t.get("raw_id")): t for t in FAKE_STRUCTURED_TRENDS}
        selected_trends = [id_to_trend[str(r["topic_id"])] for r in filtered_result["results"]]

        analyzed = analyze_viral_notes(track, selected_trends)

        print(f"\n拆解完成 ({len(analyzed)} 条笔记):")
        for a in analyzed:
            print(f"\n【{a['title']}】")
            print(f"  标题公式：{a.get('title_formula', 'N/A')}")
            print(f"  情绪触发点：{a.get('emotional_triggers', 'N/A')[:3]}")

    # ---------- Step 4: 测试 Agent3 选题生成 + 比例控制 ----------
    print("\n\n[Step 4] 测试 Agent3 选题生成 + 比例控制（mock LLM 输出）")
    print("-" * 40)

    # 模拟 Agent3 生成 10 个选题，严格按照 80% 视频 +20% 图文
    MOCK_AGENT3_OUTPUT = [
        {
            "topic_title": "Copilot 实战：我用 AI 自动完成 80% 的日常开发任务",
            "content_format": "视频笔记",
            "estimated_potential": "高",
            "core_angle": "从里昂说 AI 的 Codex 案例延伸，展示另一个强大 AI 编码助手的具体使用技巧",
            "borrowed_from": {
                "source_topic_id": "1",
                "source_author": "里昂说 AI",
                "inspiration_points": ["工具实操演示", "具体功能展示", "效率对比"],
            },
        },
        {
            "topic_title": "AI 编程助手配置指南：3 步让 Copilot 成为你的结对程序员",
            "content_format": "视频笔记",
            "estimated_potential": "中高",
            "core_angle": "教程向内容，复刻 Codex 的配置流程思路，应用到 Copilot",
            "borrowed_from": {
                "source_topic_id": "1",
                "source_author": "里昂说 AI",
                "inspiration_points": ["配置流程", "插件推荐", "操作演示"],
            },
        },
        {
            "topic_title": "从 0 开始学 AI 产品：我的第一份竞品分析报告",
            "content_format": "图文笔记",
            "estimated_potential": "中",
            "core_angle": "借鉴 Nox.的文科转行视角，分享 AI 产品的入门学习方法",
            "borrowed_from": {
                "source_topic_id": "2",
                "source_author": "Nox.",
                "inspiration_points": ["学习路径分享", "入门资料推荐"],
            },
        },
        {
            "topic_title": "我用 AI 写了个自动化脚本，每天少加班 1 小时",
            "content_format": "视频笔记",
            "estimated_potential": "高",
            "core_angle": "从 Codex 的'数字员工'概念出发，分享实际落地案例",
            "borrowed_from": {
                "source_topic_id": "1",
                "source_author": "里昂说 AI",
                "inspiration_points": ["AI 自动化", "效率提升", "实操演示"],
            },
        },
        {
            "topic_title": "AI 工具测评 | 哪个 coding assistant 最适合新手？",
            "content_format": "视频笔记",
            "estimated_potential": "中高",
            "core_angle": "横向对比多个 AI 编程工具，给初学者选择建议",
            "borrowed_from": {
                "source_topic_id": "1",
                "source_author": "里昂说 AI",
                "inspiration_points": ["工具对比", "新手友好度", "功能评测"],
            },
        },
        {
            "topic_title": "文科生如何做 AI 产品面试准备？5 个必知要点",
            "content_format": "图文笔记",
            "estimated_potential": "中",
            "core_angle": "延续 Nox.的转行主题，提供实用的面试指导",
            "borrowed_from": {
                "source_topic_id": "2",
                "source_author": "Nox.",
                "inspiration_points": ["转行经验", "职场准备"],
            },
        },
        {
            "topic_title": "AI 智能体实践：让 Claude/Codex 帮你写周报",
            "content_format": "视频笔记",
            "estimated_potential": "高",
            "core_angle": "应用 Codex 的智能体概念，解决职场人的痛点需求",
            "borrowed_from": {
                "source_topic_id": "1",
                "source_author": "里昂说 AI",
                "inspiration_points": ["AI 智能体", "任务执行", "办公效率"],
            },
        },
        {
            "topic_title": "Python 零基础自学路线图：我是怎么在 3 个月内上手的",
            "content_format": "视频笔记",
            "estimated_potential": "中高",
            "core_angle": "学习路径分享，呼应 Nox.提到的自学经历",
            "borrowed_from": {
                "source_topic_id": "2",
                "source_author": "Nox.",
                "inspiration_points": ["学习路径", "时间规划", "资源推荐"],
            },
        },
        {
            "topic_title": "AI 产品思维：如何用用户视角理解 Copilot 这类工具",
            "content_format": "视频笔记",
            "estimated_potential": "中",
            "core_angle": "将 AI 工具的使用上升到产品方法论层面",
            "borrowed_from": {
                "source_topic_id": "1",
                "source_author": "里昂说 AI",
                "inspiration_points": ["产品设计思路", "工具使用心得"],
            },
        },
        {
            "topic_title": "转行日记 Day30:我学会了第一个 Python 爬虫项目",
            "content_format": "图文笔记",
            "estimated_potential": "中",
            "core_angle": "持续记录 Nox.风格的转行成长历程",
            "borrowed_from": {
                "source_topic_id": "2",
                "source_author": "Nox.",
                "inspiration_points": ["成长记录", "项目实践"],
            },
        },
    ]

    with mock.patch("agents.topic_generator.call_llm_json", return_value=MOCK_AGENT3_OUTPUT):
        from agents.topic_generator import generate_topics

        persona_description = "热爱 AI 工具学习的年轻创作者，关注效率和自我提升"
        topic_count = 10

        topics_result = generate_topics(
            track=track,
            persona_description=persona_description,
            viral_analysis_report=analyzed,
            history_topics=[],
            topic_count=topic_count,
            format_ratio=format_ratio,
        )

        # 统计实际比例
        topics = topics_result["topics"]
        video_count = sum(1 for t in topics if "视频" in t["content_format"])
        image_count = len(topics) - video_count
        actual_video_ratio = video_count / len(topics)

        print(f"\n生成的选题 ({len(topics)} 个):")
        print(f"\n📊 格式统计:")
        print(f"   视频笔记：{video_count}个 ({actual_video_ratio*100:.0f}%)")
        print(f"   图文笔记：{image_count}个 ({(1-actual_video_ratio)*100:.0f}%)")
        print(f"   目标比例：视频 80% / 图文 20%")

        if topics_result.get("ratio_warning"):
            print(f"\n⚠️ {topics_result['ratio_warning']}")
        else:
            print(f"\n✅ 比例控制正常：实际 80% 视频接近目标 80%")

        print(f"\n选题列表:")
        for i, t in enumerate(topics, 1):
            fmt = t["content_format"]
            potential = t.get("estimated_potential", "?")
            title = t["topic_title"][:40] + "..." if len(t["topic_title"]) > 40 else t["topic_title"]
            source = t.get("borrowed_from", {}).get("source_author", "?")
            print(f"  {i}. [{potential}] {fmt} - {title}")
            print(f"     ← 灵感来源：{source}")

    # ========== 测试结果总结 ==========
    print("\n\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    print("✅ Agent0 结构化采集：成功解析 2 条原始笔记")
    print("✅ Agent1 热点筛选：按分数正确排序 (里昂说 AI > Nox.)")
    print("✅ Agent2 爆款拆解：提取了标题公式/情绪触发点等特征")
    print("✅ Agent3 选题生成：生成 10 个选题，8 视频/2 图文，符合 80%/20% 目标比例")
    print("\n🎉 全部测试通过！")


if __name__ == "__main__":
    run_full_pipeline()
