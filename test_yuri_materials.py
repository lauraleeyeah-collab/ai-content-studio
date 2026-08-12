"""
使用实际笔记内容测试小红书爆款热点工具
测试素材：
1. 里昂说 AI (9K+ 粉丝) - "codex 有多强？看完你也能用 AI 为所欲为"
   - 转发 2K+, 点赞 18K, 收藏 36K, 评论 420
2. Nox. (500+ 粉丝) - "985 文科女，勇闯 AI 产品"

笔记计划配比：80% 视频 + 20% 图文
"""
import json
from agents.trend_collector import collect_trends
from agents.trend_filter import filter_trends
from agents.viral_analyzer import analyze_viral_notes
from agents.topic_generator import generate_topics
from config import DEFAULT_FORMAT_RATIO

# ============================================================
# Step 1: 定义两条笔记的原始文本数据（从 App 复制粘贴的格式）
# ============================================================

RAW_NOTE_1 = """
【标题】codex 有多强？看完你也能用 AI 为所欲为
【作者】里昂说 AI
【粉丝数】9000+
【互动数据】转发 2K+, 点赞 18K, 收藏 36K, 评论 420
【时长】3 分钟视频

【正文】
Codex 是什么？它不是普通的聊天机器人，而是能执行任务的"数字员工"！
今天给大家详细讲解 Codex 的入门配置和基础用法，让你真正把它当作助手来使用。

🔹 Codex 的定义：
- AI 智能体，更像"员工"角色
- 会调用工具、执行指令
- 不只是聊天工具，而是实际操作

🔹 界面结构：
左侧 = 能力区（管理项目和插件）
右侧 = 工作区（对话、下指令）

🔹 操作流程：
1️⃣ 新建项目
2️⃣ 配置插件和工作模式
3️⃣ 在对话区下达任务

🔹 关键插件推荐：
✅ Computer Use（必备）
✅ Remotion（视频制作）
✅ HyperFrames（产品设计相关）

🔹 两种工作模式：
计划模式 - AI 先拆解任务、列出步骤，适合需求不明确时
目标模式 - 直接下达明确指令

#AI 工具 #codex #人工智能 #效率提升
"""

RAW_NOTE_2 = """
【标题】985 文科女，勇闯 AI 产品
【作者】Nox.
【粉丝数】500+
【互动数据】待补充（新人账号，数据偏低）
【形式】图文/视频待定

【正文】
一个 985 文科女生，如何转行做 AI 产品经理？
这是我的转型日记，记录从 0 到 1 的学习过程。

📌 背景：
- 普通院校文科专业
- 对技术一窍不通
- 但对 AI 产品充满热情

📌 学习路径：
- 自学 Python 基础
- 研究主流 AI 产品功能
- 输出学习笔记和评测

📌 内容方向：
- AI 工具开箱体验
- 产品功能深度解析
- 学习心得分享

欢迎同样想转行 AI 产品的同学一起交流！
#AI 产品经理 #转行 #文科生 #个人成长
"""

# ============================================================
# Step 2: 运行完整的 Pipeline
# ============================================================

def run_full_pipeline():
    print("=" * 80)
    print("小红书爆款热点工具 - 测试开始")
    print("测试素材：里昂说 AI(9K 粉)+Nox.(500 粉)")
    print("配比要求：80% 视频 + 20% 图文")
    print("=" * 80)

    track = "AI 工具/个人成长"
    format_ratio = {"视频笔记": 0.8, "图文笔记": 0.2}  # 80% 视频 +20% 图文

    # ---------- Step 1: 采集结构化 ----------
    print("\n[Step 1] 采集结构化 (Agent0)")
    print("-" * 40)

    raw_text_blob = RAW_NOTE_1 + "\n\n---分割线---\n\n" + RAW_NOTE_2

    try:
        structured = collect_trends(track, raw_text_blob)
        print(f"成功提取 {len(structured)} 条笔记：")
        for i, item in enumerate(structured, 1):
            print(f"\n{i}. 标题：{item.get('title', 'N/A')}")
            print(f"   作者：{item.get('author', 'N/A')}")
            print(f"   粉丝数：{item.get('follower_count', 'N/A')}")
            print(f"   点赞：{item.get('likes', 'N/A')}, 收藏：{item.get('collections', 'N/A')}")

    except Exception as e:
        print(f"采集失败：{e}")
        return

    # ---------- Step 2: 热点筛选 ----------
    print("\n\n[Step 2] 热点筛选 (Agent1)")
    print("-" * 40)

    try:
        filtered_result = filter_trends(track, structured, top_n=10)

        if filtered_result.get("batch_warning"):
            print(f"⚠️ 预警：{filtered_result['batch_warning']}")

        print(f"\n筛选结果 ({len(filtered_result['results'])} 条):")
        for r in sorted(filtered_result["results"], key=lambda x: x["total_score"], reverse=True):
            score_info = f"总分:{r['total_score']} | 置信度:{r['scoring_confidence']}"
            print(f"\n【{r['title']}】")
            print(f"  {score_info}")
            print(f"  评分详情:")
            for dim, score in r["scores"].items():
                marker = "✓" if score else "?"
                print(f"    {marker} {dim}: {score}")

    except Exception as e:
        print(f"筛选失败：{e}")
        return

    # ---------- Step 3: 爆款拆解 ----------
    print("\n\n[Step 3] 爆款拆解 (Agent2)")
    print("-" * 40)

    try:
        # 把筛选结果的 topic_id 对应回原始结构化数据
        id_to_trend = {str(t.get("raw_id")): t for t in structured}
        selected_trends = []
        for r in filtered_result["results"]:
            full = id_to_trend.get(str(r["topic_id"]))
            if full:
                selected_trends.append(full)

        analyzed = analyze_viral_notes(track, selected_trends)

        print(f"拆解完成 ({len(analyzed)} 条笔记):")
        for a in analyzed:
            print(f"\n【{a['title']}】")
            print(f"  标题公式：{a.get('title_formula', 'N/A')}")
            print(f"  内容结构：{a.get('content_structure', 'N/A')}")
            print(f"  情绪触发点：{a.get('emotional_triggers', 'N/A')}")
            print(f"  互动话术：{a.get('interaction_tactics', 'N/A')}")

    except Exception as e:
        print(f"拆解失败：{e}")
        return


if __name__ == "__main__":
    run_full_pipeline()
    print("\n" + "=" * 80)
    print("测试结束")
    print("=" * 80)
