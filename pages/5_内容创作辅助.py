"""
内容创作辅助 — 标题优化、A/B测试、标签推荐、文案诊断
"""
import json
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    import plotly.graph_objects as go
except ImportError:
    go = None

from agents.title_optimizer import generate_title_variants, score_title_variants
from agents.hashtag_recommender import recommend_hashtags
from agents.note_scorer import score_single_note
from database import db_utils
from utils.ui_components import (
    inject_custom_css,
    render_radar_chart,
    render_dimension_card,
    render_score_bar,
    render_priority_list,
    DIMENSION_LABELS,
)
from utils.demo_data import render_demo_toggle

st.set_page_config(page_title="内容创作辅助", layout="wide")
inject_custom_css()

# ── 初始化 ──
db_utils.init_db()

# ── 侧栏 ──
with st.sidebar:
    st.markdown('<div class="sidebar-header">全局配置</div>', unsafe_allow_html=True)
    render_demo_toggle()
    api_key = st.text_input("DashScope API Key", type="password",
                            value=os.environ.get("DASHSCOPE_API_KEY", ""))
    if api_key:
        os.environ["DASHSCOPE_API_KEY"] = api_key
    track = st.text_input("赛道关键词", value="AI工具/自我提升")
    persona = st.text_area("账号人设描述(可选)", value="", height=100)

# ── 页面标题 ──
st.markdown(
    '<div class="page-header"><h1>内容创作辅助</h1>'
    '<p>标题优化、A/B测试、标签推荐、文案诊断,全方位提升内容质量</p></div>',
    unsafe_allow_html=True,
)

# ── 四个子Tab ──
tab1, tab2, tab3, tab4 = st.tabs(["标题优化", "标题A/B测试", "标签推荐", "文案诊断"])

# ═══════════════════════════════════════════
# Tab 1: 标题优化
# ═══════════════════════════════════════════
with tab1:
    st.subheader("生成优化标题变体")

    with st.form("title_gen_form"):
        original_title = st.text_input("原始标题", placeholder="输入当前标题...")

        # 使用新的图像粘贴输入组件替代原来的文本区域
        from utils.image_paste_handler import render_image_paste_input, get_image_input_state, clear_image_input
        topic_context, topic_images = render_image_paste_input("笔记主题/内容概要", key="topic_context_input", height=100)

        variant_count = st.slider("生成变体数量", min_value=3, max_value=8, value=5)
        gen_submitted = st.form_submit_button("生成标题变体", type="primary")

    if gen_submitted and original_title:
        # 获取图像输入状态
        topic_context, topic_images = get_image_input_state("topic_context_input")

        with st.spinner("AI正在生成标题变体..."):
            try:
                variants = generate_title_variants(
                    track, original_title, topic_context, persona, variant_count
                )
                st.session_state["title_variants"] = variants
                st.session_state["title_original"] = original_title
                st.session_state["title_context"] = topic_context
                st.success(f"生成了 {len(variants)} 个标题变体!")

                # 清除图像输入内容
                clear_image_input("topic_context_input")
            except Exception as e:
                st.error(f"生成失败: {e}")

    # 展示变体
    variants = st.session_state.get("title_variants", [])
    if variants:
        st.markdown("### 标题变体")
        for i, v in enumerate(variants, 1):
            st.write(f"**{i}.** {v.get('title', '')}  [{v.get('formula_type', '')}]")
            st.caption(f"  理由: {v.get('rationale', '')}")

        # 评分按钮
        if st.button("对所有变体评分", key="btn_score_variants"):
            with st.spinner("AI正在评分..."):
                try:
                    scored = score_title_variants(
                        track, variants, st.session_state.get("title_context", "")
                    )
                    st.session_state["title_scored"] = scored

                    # 保存
                    db_utils.save_title_optimization(
                        track,
                        st.session_state.get("title_original", ""),
                        st.session_state.get("title_context", ""),
                        json.dumps(scored, ensure_ascii=False),
                    )
                except Exception as e:
                    st.error(f"评分失败: {e}")

    # 评分结果
    scored = st.session_state.get("title_scored", [])
    if scored:
        st.markdown("### 评分结果")

        # 柱状图对比
        if go:
            fig = go.Figure(go.Bar(
                x=[s["title"][:20] for s in scored],
                y=[s["total_score"] for s in scored],
                marker_color=[
                    "#52C41A" if s["verdict"] == "推荐"
                    else "#1890FF" if s["verdict"] == "可用"
                    else "#FF4D4F"
                    for s in scored
                ],
            ))
            fig.update_layout(title="标题评分对比", yaxis_title="总分(满分100)",
                              height=300, margin=dict(t=40, b=60))
            st.plotly_chart(fig, width="stretch")

        # 详细表格
        for s in scored:
            verdict = s.get("verdict", "")
            color = {"推荐": "green", "可用": "blue", "不推荐": "red"}.get(verdict, "gray")
            st.markdown(
                f"**#{s.get('rank', '')}** {s.get('title', '')}  "
                f"**总分: {s.get('total_score', 0)}**  "
                f"<span style='color:{color}; font-weight:bold;'>{verdict}</span>",
                unsafe_allow_html=True,
            )
            scores = s.get("scores", {})
            score_parts = [f"{k.replace('_', ' ')}: {v}" for k, v in scores.items()]
            st.caption(" | ".join(score_parts))

# ═══════════════════════════════════════════
# Tab 2: 标题A/B测试
# ═══════════════════════════════════════════
with tab2:
    st.subheader("标题A/B对比测试")
    st.write("输入2-6个标题候选,进行评分对比。")

    # 动态标题输入
    if "ab_title_count" not in st.session_state:
        st.session_state.ab_title_count = 3

    ab_titles = []
    for i in range(st.session_state.ab_title_count):
        t = st.text_input(f"标题候选 {i+1}", key=f"ab_title_{i}")
        if t.strip():
            ab_titles.append(t.strip())

    c1, c2 = st.columns(2)
    with c1:
        if st.button("+ 添加候选", key="btn_add_ab") and st.session_state.ab_title_count < 6:
            st.session_state.ab_title_count += 1
            st.rerun()
    with c2:
        if st.button("- 减少候选", key="btn_del_ab") and st.session_state.ab_title_count > 2:
            st.session_state.ab_title_count -= 1
            st.rerun()

    ab_context = st.text_input("笔记主题(可选)", key="ab_context")

    if st.button("评分对比", key="btn_score_ab", type="primary", disabled=(len(ab_titles) < 2)):
        with st.spinner("AI正在评分..."):
            try:
                ab_scored = score_title_variants(track, ab_titles, ab_context)
                st.session_state["ab_result"] = ab_scored
            except Exception as e:
                st.error(f"评分失败: {e}")

    # A/B结果
    ab_result = st.session_state.get("ab_result", [])
    if ab_result:
        st.markdown("### 对比结果")

        # 雷达图叠加
        if go and len(ab_result) >= 2:
            fig = go.Figure()
            colors = ["#FF2442", "#1890FF", "#52C41A", "#FA8C16", "#722ED1", "#13C2C2"]
            for i, s in enumerate(ab_result[:6]):
                scores = s.get("scores", {})
                dims = list(scores.keys())
                vals = [scores.get(d, 0) for d in dims]
                vals.append(vals[0])  # 闭合
                dim_labels = [d.replace("_", " ").title() for d in dims]
                dim_labels.append(dim_labels[0])
                fig.add_trace(go.Scatterpolar(
                    r=vals, theta=dim_labels,
                    name=f"#{s.get('rank', i+1)} {s.get('title', '')[:15]}",
                    fill="toself" if i == 0 else None,
                    line=dict(color=colors[i % len(colors)]),
                    opacity=0.7,
                ))
            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
                title="标题评分雷达对比",
                height=450,
                showlegend=True,
                legend=dict(orientation="h", y=-0.1),
            )
            st.plotly_chart(fig, width="stretch")

        # 冠军
        winner = ab_result[0]
        st.success(f"**冠军:** {winner.get('title', '')} (总分: {winner.get('total_score', 0)})")

        for s in ab_result:
            verdict = s.get("verdict", "")
            st.write(
                f"**#{s.get('rank', '')}** {s.get('title', '')} "
                f"— 总分 {s.get('total_score', 0)} [{verdict}]"
            )

# ═══════════════════════════════════════════
# Tab 3: 标签推荐
# ═══════════════════════════════════════════
with tab3:
    st.subheader("智能标签推荐")

    with st.form("hashtag_form"):
        ht_title = st.text_input("笔记标题", key="ht_title")

        # 使用新的图像粘贴输入组件替代原来的文本区域
        from utils.image_paste_handler import render_image_paste_input, get_image_input_state, clear_image_input
        ht_body, ht_images = render_image_paste_input("笔记正文(前300字即可)", key="ht_body_input", height=150)

        col1, col2 = st.columns(2)
        with col1:
            ht_type = st.selectbox("笔记类型", ["图文笔记", "视频笔记"], key="ht_type")
        with col2:
            ht_count = st.slider("推荐标签数量", min_value=5, max_value=12, value=8, key="ht_count")
        ht_existing = st.text_input("已有标签(逗号分隔,可选)", key="ht_existing")
        ht_submitted = st.form_submit_button("推荐标签", type="primary")

    if ht_submitted and ht_title:
        # 获取图像输入状态
        ht_body, ht_images = get_image_input_state("ht_body_input")

        existing = [t.strip() for t in ht_existing.split(",") if t.strip()] if ht_existing else []
        with st.spinner("AI正在推荐标签..."):
            try:
                ht_result = recommend_hashtags(
                    track, ht_title, ht_body, ht_type, existing, ht_count
                )
                st.session_state["hashtag_result"] = ht_result
                st.session_state["hashtag_input"] = {
                    "title": ht_title, "note_type": ht_type,
                }

                # 保存
                db_utils.save_hashtag_recommendation(
                    track, ht_title, ht_type,
                    json.dumps(ht_result, ensure_ascii=False),
                )

                # 清除图像输入内容
                clear_image_input("ht_body_input")
            except Exception as e:
                st.error(f"推荐失败: {e}")

    ht_result = st.session_state.get("hashtag_result")
    if ht_result:
        st.markdown("### 推荐标签")

        # 混合警告
        if ht_result.get("mix_warning"):
            st.warning(ht_result["mix_warning"])

        # 标签卡片
        category_colors = {"大词": "red", "中词": "orange", "小词": "green"}
        for tag_info in ht_result.get("recommended_hashtags", []):
            tag = tag_info.get("tag", "")
            cat = tag_info.get("category", "")
            heat = tag_info.get("estimated_heat", "")
            rationale = tag_info.get("rationale", "")
            score = tag_info.get("relevance_score", 0)
            color = category_colors.get(cat, "gray")

            st.markdown(
                f"**#{tag}** &nbsp; "
                f"<span style='color:{color}; font-size:12px;'>[{cat}]</span> &nbsp; "
                f"<span style='font-size:12px;'>热度:{heat}</span> &nbsp; "
                f"<span style='font-size:12px;'>相关度:{score}/10</span>",
                unsafe_allow_html=True,
            )
            st.caption(f"  {rationale}")

        # 策略说明
        if ht_result.get("strategy_note"):
            st.markdown("### 标签策略说明")
            st.info(ht_result["strategy_note"])

        # 避免使用的标签
        avoid = ht_result.get("avoid_tags", [])
        if avoid:
            st.markdown("### 不建议使用的标签")
            for a in avoid:
                st.warning(a)

        # 一键复制
        all_tags = " ".join(
            f"#{t.get('tag', '')}" for t in ht_result.get("recommended_hashtags", [])
        )
        st.markdown("### 一键复制")
        st.code(all_tags, language=None)

# ═══════════════════════════════════════════
# Tab 4: 文案诊断
# ═══════════════════════════════════════════
with tab4:
    st.subheader("文案质量诊断")

    # 截图上传 → 自动预填
    diag_mode = st.radio("输入方式", ["截图上传", "手动填写"], horizontal=True, key="diag_mode")

    diag_prefill = {}
    if diag_mode == "截图上传":
        st.caption("支持三种方式添加截图: Cmd+V 粘贴 / 拖拽图片 / 点击选择文件")
        from utils.paste_capture import render_paste_zone, images_to_vision_input
        captured_images = render_paste_zone(key_prefix="diag_paste")
        if captured_images and st.button("从截图识别", key="btn_diag_extract", type="primary"):
            from agents.image_extractor import extract_from_images
            images_bytes = images_to_vision_input(captured_images)
            with st.spinner("AI正在识别截图..."):
                try:
                    extracted = extract_from_images(track, images_bytes)
                    if extracted:
                        st.session_state["diag_prefill"] = extracted[0]
                        st.success("识别成功! 请检查下方预填信息后点击诊断。")
                        st.rerun()
                except Exception as e:
                    st.error(f"识别失败: {e}")
        diag_prefill = st.session_state.get("diag_prefill", {})

    # 新增支持在输入框中直接粘贴图片的功能
    from utils.image_paste_handler import render_image_paste_input, get_image_input_state, clear_image_input

    with st.form("diagnose_form"):
        diag_title = st.text_input("笔记标题", key="diag_title", value=diag_prefill.get("title", ""))

        # 使用新的图像粘贴输入组件
        diag_body, diag_images = render_image_paste_input("笔记正文", key="diag_body_input", height=250)

        # 如果有预填充内容，更新输入框
        if diag_prefill.get("body_text"):
            st.session_state["diag_body_input_text"] = diag_prefill.get("body_text", "")

        col1, col2 = st.columns(2)
        with col1:
            diag_type = st.selectbox("笔记类型", ["图文笔记", "视频笔记", "未知"], key="diag_type")
        with col2:
            prefill_tags = diag_prefill.get("hashtags", [])
            tags_str = ", ".join(prefill_tags) if isinstance(prefill_tags, list) else ""
            diag_hashtags = st.text_input("标签(逗号分隔,可选)", key="diag_hashtags", value=tags_str)
        diag_submitted = st.form_submit_button("诊断评分", type="primary")

    if diag_submitted and diag_title:
        # 获取图像输入状态
        diag_body, diag_images = get_image_input_state("diag_body_input")

        note_data = {
            "title": diag_title,
            "body_text": diag_body,
            "hashtags": [t.strip() for t in diag_hashtags.split(",") if t.strip()] if diag_hashtags else [],
            "likes": None, "comments": None, "collects": None, "shares": None,
            "note_type": diag_type,
            "cover_description": None,
        }
        with st.spinner("AI正在诊断..."):
            try:
                diag_result = score_single_note(track, note_data, persona or None)
                st.session_state["diagnose_result"] = diag_result
                st.success("诊断完成!")

                # 清除图像输入内容
                clear_image_input("diag_body_input")
            except Exception as e:
                st.error(f"诊断失败: {e}")

    diag_result = st.session_state.get("diagnose_result")
    if diag_result:
        scores = diag_result["scores"]

        # 等级 + 雷达图
        c1, c2 = st.columns([1, 2])
        with c1:
            from utils.ui_components import render_grade_badge
            render_grade_badge(diag_result["grade"], diag_result["total_score"])
        with c2:
            score_values = {k: v["score"] for k, v in scores.items() if v["score"] is not None}
            fig = render_radar_chart(score_values, "文案质量诊断")
            if fig:
                st.plotly_chart(fig, width="stretch")

        # 各维度详情
        st.markdown("### 各维度详情")
        col1, col2 = st.columns(2)
        for i, key in enumerate(DIMENSION_LABELS.keys()):
            target = col1 if i % 2 == 0 else col2
            with target:
                if key in scores:
                    render_dimension_card(key, scores[key])
                    render_score_bar(DIMENSION_LABELS[key], scores[key]["score"] or 0)

        # 改进方向
        priorities = diag_result.get("improvement_priorities", [])
        if priorities:
            st.markdown("### 优先改进方向")
            render_priority_list(priorities)
