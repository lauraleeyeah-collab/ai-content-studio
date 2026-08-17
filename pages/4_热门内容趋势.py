"""
热门内容趋势分析 — 品类级趋势分析,标签共现图谱,发现内容空白
"""
import json
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    import plotly.graph_objects as go
    import plotly.express as px
except ImportError:
    go = None
    px = None

from agents.trend_summarizer import summarize_trends
from agents.trend_collector import collect_trends
from database import db_utils
from utils.ui_components import inject_custom_css, render_trend_card
from utils.demo_data import render_demo_toggle

st.set_page_config(page_title="热门内容趋势", layout="wide")
inject_custom_css()

# ── 初始化 ──
db_utils.init_db()
if "trend_result" not in st.session_state:
    st.session_state.trend_result = None
if "trend_notes" not in st.session_state:
    st.session_state.trend_notes = []

# ── 侧栏 ──
with st.sidebar:
    st.markdown('<div class="sidebar-header">全局配置</div>', unsafe_allow_html=True)
    render_demo_toggle()
    api_key = st.text_input("DashScope API Key", type="password",
                            value=os.environ.get("DASHSCOPE_API_KEY", ""))
    if api_key:
        os.environ["DASHSCOPE_API_KEY"] = api_key
    track = st.text_input("赛道关键词", value="AI工具/自我提升")

# ── 页面标题 ──
st.markdown(
    '<div class="page-header"><h1>热门内容趋势分析</h1>'
    '<p>品类级趋势分析,标签共现图谱,发现内容空白与爆款规律</p></div>',
    unsafe_allow_html=True,
)

# ── 输入区域 ──
st.subheader("输入热门笔记数据")

time_range = st.selectbox("时间范围", ["最近7天", "最近14天", "最近30天", "自定义"])

tab_img, tab_paste, tab_pipeline = st.tabs(["截图上传", "粘贴笔记文本", "从流水线导入"])

with tab_img:
    st.caption("支持三种方式添加截图: Cmd+V 粘贴 / 拖拽图片 / 点击选择文件")
    from utils.paste_capture import render_paste_zone, images_to_vision_input
    captured_images = render_paste_zone(key_prefix="trend_paste")
    if captured_images and st.button("从截图识别笔记", key="btn_extract_trend_img", type="primary"):
        from agents.image_extractor import extract_from_images
        images_bytes = images_to_vision_input(captured_images)
        with st.spinner(f"AI正在识别{len(images_bytes)}张截图..."):
            try:
                extracted = extract_from_images(track, images_bytes)
                st.session_state.trend_notes = extracted
                st.success(f"成功识别 {len(extracted)} 条笔记!")
            except Exception as e:
                st.error(f"识别失败: {e}")

with tab_paste:
    raw_text = st.text_area(
        "粘贴热门笔记原始文本(建议10条以上)",
        height=300,
        placeholder="从小红书App复制的热门笔记内容...",
        key="trend_raw_text",
    )
    if st.button("提取笔记", key="btn_extract_trend", type="primary"):
        if not raw_text.strip():
            st.warning("请先粘贴笔记内容。")
        else:
            with st.spinner("正在提取..."):
                try:
                    extracted = collect_trends(track, raw_text)
                    st.session_state.trend_notes = extracted
                    st.success(f"成功提取 {len(extracted)} 条笔记!")
                except Exception as e:
                    st.error(f"提取失败: {e}")

with tab_pipeline:
    pipeline_data = st.session_state.pipeline.get("structured_trends") if "pipeline" in st.session_state else None
    if pipeline_data:
        st.info(f"流水线中已有 {len(pipeline_data)} 条笔记数据。")
        if st.button("导入流水线数据", key="btn_import_trend"):
            st.session_state.trend_notes = pipeline_data
            st.success(f"已导入 {len(pipeline_data)} 条笔记!")
    else:
        st.info("流水线中暂无数据。")

notes = st.session_state.trend_notes
if notes:
    st.info(f"当前共 {len(notes)} 条笔记待分析。")

# ── 分析按钮 ──
if st.button("开始趋势分析", type="primary", disabled=(not notes), key="btn_analyze_trend"):
    with st.spinner("AI正在分析内容趋势..."):
        try:
            result = summarize_trends(track, notes, time_range)
            st.session_state.trend_result = result

            # 保存快照
            db_utils.save_trend_snapshot(
                track=track,
                time_range=time_range,
                notes_count=len(notes),
                computed_stats_json=json.dumps(result["computed_stats"], ensure_ascii=False),
                llm_summary_json=json.dumps(result["llm_summary"], ensure_ascii=False),
            )
            st.success("趋势分析完成!")
        except Exception as e:
            st.error(f"分析失败: {e}")

# ── 结果展示 ──
result = st.session_state.trend_result
if result:
    stats = result["computed_stats"]
    llm = result["llm_summary"]

    st.markdown("---")
    st.subheader("数据概览")

    # 指标卡片
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("分析笔记数", stats.get("total_notes", 0))
    m2.metric("平均互动量", stats.get("avg_engagement", 0))
    m3.metric("爆款阈值(90分位)", stats.get("high_engagement_threshold", 0))
    format_ratio = stats.get("content_format_ratio", {})
    dominant_format = max(format_ratio, key=format_ratio.get) if format_ratio else "未知"
    m4.metric("主导内容形式", f"{dominant_format} ({format_ratio.get(dominant_format, 0)}篇)")

    # 图表行1
    st.markdown("### 数据分布图表")
    c1, c2 = st.columns(2)

    with c1:
        # 互动分布直方图
        dist = stats.get("engagement_distribution", {})
        if go and dist:
            fig_hist = go.Figure(go.Bar(
                x=list(dist.keys()),
                y=list(dist.values()),
                marker_color="#FF2442",
            ))
            threshold = stats.get("high_engagement_threshold", 0)
            fig_hist.update_layout(
                title="互动量分布",
                xaxis_title="互动量区间",
                yaxis_title="笔记数",
                height=350,
                margin=dict(t=40, b=40),
                annotations=[dict(
                    x=list(dist.keys())[-1] if threshold > 2000 else list(dist.keys())[2],
                    y=max(dist.values()) * 0.8,
                    text=f"爆款阈值: {threshold}",
                    showarrow=True,
                    font=dict(color="#FF2442"),
                )] if threshold else [],
            )
            st.plotly_chart(fig_hist, width="stretch")

    with c2:
        # 内容形式分布
        if go and format_ratio:
            fig_pie = go.Figure(go.Pie(
                labels=list(format_ratio.keys()),
                values=list(format_ratio.values()),
                marker=dict(colors=["#FF2442", "#FF6B81", "#FFB3C1"]),
            ))
            fig_pie.update_layout(title="内容形式比例", height=350, margin=dict(t=40, b=20))
            st.plotly_chart(fig_pie, width="stretch")

    # 图表行2
    c3, c4 = st.columns(2)

    with c3:
        # Top 标签频率
        top_tags = stats.get("hashtag_frequency", [])
        if go and top_tags:
            tags_for_chart = top_tags[:15]
            fig_tags = go.Figure(go.Bar(
                y=[t["tag"] for t in reversed(tags_for_chart)],
                x=[t["count"] for t in reversed(tags_for_chart)],
                orientation="h",
                marker_color="#FF2442",
            ))
            fig_tags.update_layout(title="Top 15 热门标签", height=400, margin=dict(t=40, b=20))
            st.plotly_chart(fig_tags, width="stretch")

    with c4:
        # 标题公式分布
        formula_freq = stats.get("title_formula_frequency", {})
        if go and formula_freq:
            fig_formula = go.Figure(go.Bar(
                x=list(formula_freq.keys()),
                y=list(formula_freq.values()),
                marker_color=["#FF2442", "#FF6B81", "#FA8C16", "#52C41A", "#1890FF", "#999999"],
            ))
            fig_formula.update_layout(
                title="标题公式类型分布",
                xaxis_title="公式类型",
                yaxis_title="数量",
                height=400,
                margin=dict(t=40, b=40),
            )
            st.plotly_chart(fig_formula, width="stretch")

    # 标签共现
    cooccurrence = stats.get("hashtag_cooccurrence", [])
    if cooccurrence:
        st.markdown("### 标签共现关系 Top 10")
        for co in cooccurrence:
            pair = co.get("pair", [])
            count = co.get("count", 0)
            if len(pair) == 2:
                st.text(f"  {pair[0]} + {pair[1]}  (共现 {count} 次)")

    # LLM趋势总结
    st.markdown("---")
    st.subheader("AI 趋势洞察")

    c1, c2 = st.columns(2)
    with c1:
        # 主导主题
        themes = llm.get("dominant_themes", [])
        if themes:
            render_trend_card("主导主题", "、".join(themes), direction="neutral")

        # 兴起趋势
        if llm.get("emerging_patterns"):
            render_trend_card("兴起趋势", llm["emerging_patterns"], direction="up")

        # 衰退趋势
        if llm.get("declining_patterns"):
            render_trend_card("衰退趋势", llm["declining_patterns"], direction="down")

    with c2:
        # 爆款公式
        formulas = llm.get("viral_formulas", [])
        if formulas:
            formula_text = ""
            for f in formulas:
                formula_text += f"**{f.get('formula', '')}** (出现{f.get('evidence_count', 0)}次)\n"
                for t in f.get("example_titles", [])[:2]:
                    formula_text += f"  例: {t}\n"
            render_trend_card("爆款公式", formula_text, direction="neutral")

        # 内容空白
        if llm.get("content_gaps"):
            render_trend_card("内容空白(机会)", llm["content_gaps"], direction="up")

    # 战略总结
    if llm.get("strategic_summary"):
        st.markdown("### 战略总结")
        st.info(llm["strategic_summary"])

    # 形式建议
    if llm.get("format_recommendations"):
        st.markdown("### 内容形式建议")
        st.write(llm["format_recommendations"])

# ── 历史记录 ──
st.markdown("---")
st.subheader("历史趋势快照")
try:
    snapshots = db_utils.get_trend_snapshots(track=track, limit=5)
    if snapshots:
        for snap in snapshots:
            with st.expander(f"[{snap['time_range']}] {snap['track']} - {snap['notes_count']}条笔记 ({snap['created_at'][:16]})"):
                try:
                    llm_data = json.loads(snap["llm_summary_json"])
                    st.write(f"**战略总结:** {llm_data.get('strategic_summary', '')}")
                    themes = llm_data.get("dominant_themes", [])
                    if themes:
                        st.write(f"**主导主题:** {', '.join(themes)}")
                except (json.JSONDecodeError, AttributeError):
                    st.json(snap)
    else:
        st.info("暂无历史快照。")
except Exception:
    st.info("暂无历史快照。")
