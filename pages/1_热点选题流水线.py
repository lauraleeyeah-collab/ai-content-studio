"""
热点选题流水线 — 5步Agent流水线
采集结构化(Agent0) → 热点筛选(Agent1) → 爆款拆解(Agent2)
→ 选题生成(Agent3) → 文案生成(Agent4)

每一步结果都单独展示,支持人工检查、编辑后再进入下一步。
"""
import json
import os
import sys

import streamlit as st

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.trend_collector import collect_trends
from agents.trend_filter import filter_trends
from agents.viral_analyzer import analyze_viral_notes
from agents.topic_generator import generate_topics
from agents.copywriter import generate_copy
from database import db_utils
from config import DEFAULT_TOP_N, DEFAULT_TOPIC_COUNT, DEFAULT_FORMAT_RATIO
from utils.ui_components import inject_custom_css
from utils.demo_data import render_demo_toggle, DEMO_RAW_TEXT

DEFAULT_PERSONA = (
    "人设:深圳搞钱女孩,定位是借助AI工具辅助工作效率和个人成长,内容覆盖英语学习、阅读、"
    "职场发展、理财、搞钱副业、自律习惯六个方向,内容配比为干货80%+情绪20%。"
    "目标人群:大学生和职场人士,核心诉求是用AI实现自我提升和收入增长。"
)

st.set_page_config(page_title="热点选题流水线", layout="wide")
inject_custom_css()


def _load_default_style_guide() -> str:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "style_samples", "style_guide_v2.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


# ── 初始化 ──
if "pipeline" not in st.session_state:
    st.session_state.pipeline = {}

db_utils.init_db()

st.markdown('<div class="page-header"><h1>热点选题流水线</h1>'
            '<p>采集结构化 → 热点筛选 → 爆款拆解 → 选题生成 → 文案生成,每一步都可以人工检查后再继续</p></div>',
            unsafe_allow_html=True)

# ── 侧栏配置 ──
with st.sidebar:
    st.markdown('<div class="sidebar-header">基础配置</div>', unsafe_allow_html=True)
    render_demo_toggle()
    api_key_input = st.text_input(
        "DashScope API Key",
        type="password",
        value=os.environ.get("DASHSCOPE_API_KEY", ""),
        help="在阿里云百炼/DashScope控制台获取。",
    )
    if api_key_input:
        os.environ["DASHSCOPE_API_KEY"] = api_key_input

    track = st.text_input("赛道关键词", value="AI工具/自我提升")
    persona_description = st.text_area("账号人设描述", value=DEFAULT_PERSONA, height=140)
    style_guide = st.text_area(
        "风格特征说明(style_guide,可直接编辑迭代)",
        value=_load_default_style_guide(),
        height=200,
    )
    top_n = st.slider("热点筛选保留数量", min_value=5, max_value=30, value=DEFAULT_TOP_N)
    topic_count = st.slider("选题生成数量", min_value=3, max_value=20, value=DEFAULT_TOPIC_COUNT)
    video_ratio = st.slider(
        "视频笔记目标占比", min_value=0.0, max_value=1.0, value=DEFAULT_FORMAT_RATIO["视频笔记"]
    )
    format_ratio = {"视频笔记": video_ratio, "图文笔记": round(1 - video_ratio, 2)}

# ── 五步流水线 ──
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Step1 热点提取", "Step2 热点筛选", "Step3 爆款拆解", "Step4 选题生成", "Step5 文案生成"]
)

# ---------- Step 1: 采集结构化 ----------
with tab1:
    st.subheader("粘贴小红书笔记原始内容")
    # 演示模式的一键填充：必须在 text_area 实例化之前写入 session_state
    if st.session_state.get("demo_fill_raw_text"):
        st.session_state["raw_text_blob"] = DEMO_RAW_TEXT
        del st.session_state["demo_fill_raw_text"]
    raw_text_blob = st.text_area(
        "支持一次粘贴多条笔记,格式不需要提前整理",
        height=250,
        placeholder="把从小红书App里复制的标题、正文、点赞收藏数据等直接粘贴进来...",
        key="raw_text_blob",
    )
    if st.session_state.get("demo_mode"):
        fill_col, _ = st.columns([1, 3])
        if fill_col.button("一键填入示例笔记", key="btn_fill_demo_text"):
            st.session_state["demo_fill_raw_text"] = True
            st.rerun()
    if st.button("提取并结构化", key="btn_collect", type="primary"):
        if not raw_text_blob.strip():
            st.warning("请先粘贴笔记原始内容。")
        else:
            with st.spinner("正在提取结构化信息..."):
                try:
                    structured = collect_trends(track, raw_text_blob)
                    st.session_state.pipeline["structured_trends"] = structured
                    st.success(f"成功提取{len(structured)}条笔记。")
                except Exception as e:
                    st.error(f"提取失败:{e}")

    structured = st.session_state.pipeline.get("structured_trends")
    if structured:
        st.write("提取结果(可在下方JSON里直接修正,点击保存后生效):")
        edited = st.text_area(
            "structured_trends_json",
            value=json.dumps(structured, ensure_ascii=False, indent=2),
            height=300,
            label_visibility="collapsed",
        )
        if st.button("保存修改", key="btn_save_structured"):
            try:
                st.session_state.pipeline["structured_trends"] = json.loads(edited)
                st.success("已保存修改。")
            except json.JSONDecodeError as e:
                st.error(f"JSON格式有误,未保存:{e}")

# ---------- Step 2: 热点筛选 ----------
with tab2:
    structured = st.session_state.pipeline.get("structured_trends")
    if not structured:
        st.info("请先完成Step1热点提取。")
    else:
        if st.button("开始筛选", key="btn_filter", type="primary"):
            with st.spinner("正在打分筛选..."):
                try:
                    result = filter_trends(track, structured, top_n=top_n)
                    st.session_state.pipeline["filtered"] = result
                except Exception as e:
                    st.error(f"筛选失败:{e}")

        filtered = st.session_state.pipeline.get("filtered")
        if filtered:
            if filtered.get("batch_warning"):
                st.warning(filtered["batch_warning"])
            for r in filtered["results"]:
                with st.expander(f"[{r['total_score']}分] {r['title']}"):
                    st.json(r)

# ---------- Step 3: 爆款拆解 ----------
with tab3:
    filtered = st.session_state.pipeline.get("filtered")
    structured = st.session_state.pipeline.get("structured_trends") or []
    if not filtered:
        st.info("请先完成Step2热点筛选。")
    else:
        if st.button("开始爆款拆解", key="btn_analyze", type="primary"):
            with st.spinner("正在拆解爆款结构..."):
                try:
                    id_to_trend = {str(t.get("raw_id")): t for t in structured}
                    selected_trends = []
                    for r in filtered["results"]:
                        full = id_to_trend.get(str(r["topic_id"]))
                        if full:
                            selected_trends.append(full)
                    analyzed = analyze_viral_notes(track, selected_trends)
                    st.session_state.pipeline["analyzed"] = analyzed
                except Exception as e:
                    st.error(f"拆解失败:{e}")

        analyzed = st.session_state.pipeline.get("analyzed")
        if analyzed:
            for a in analyzed:
                with st.expander(f"{a['title']}"):
                    st.json(a)

# ---------- Step 4: 选题生成 ----------
with tab4:
    analyzed = st.session_state.pipeline.get("analyzed")
    if not analyzed:
        st.info("请先完成Step3爆款拆解。")
    else:
        if st.button("生成选题", key="btn_topics", type="primary"):
            with st.spinner("正在生成选题..."):
                try:
                    history = db_utils.get_history_topics(track)
                    result = generate_topics(
                        track,
                        persona_description,
                        analyzed,
                        history_topics=history,
                        topic_count=topic_count,
                        format_ratio=format_ratio,
                    )
                    st.session_state.pipeline["topics"] = result
                except Exception as e:
                    st.error(f"选题生成失败:{e}")

        topics_result = st.session_state.pipeline.get("topics")
        if topics_result:
            if topics_result.get("ratio_warning"):
                st.warning(topics_result["ratio_warning"])
            for t in topics_result["topics"]:
                with st.expander(f"[{t.get('estimated_potential', '?')}] {t.get('topic_title', '')}"):
                    st.json(t)

# ---------- Step 5: 文案生成 ----------
with tab5:
    topics_result = st.session_state.pipeline.get("topics")
    analyzed = st.session_state.pipeline.get("analyzed") or []
    if not topics_result:
        st.info("请先完成Step4选题生成。")
    else:
        options = [t["topic_title"] for t in topics_result["topics"]]
        choice = st.selectbox("选择一个选题生成文案", options)
        selected_topic = next(t for t in topics_result["topics"] if t["topic_title"] == choice)

        if st.button("生成文案", key="btn_copy", type="primary"):
            with st.spinner("正在生成文案..."):
                try:
                    source_id = selected_topic.get("borrowed_from", {}).get("source_topic_id")
                    viral_ref = next(
                        (a for a in analyzed if str(a.get("topic_id")) == str(source_id)),
                        analyzed[0] if analyzed else {},
                    )
                    copy_text = generate_copy(
                        track, persona_description, selected_topic, viral_ref, style_guide
                    )
                    st.session_state.pipeline["copy_text"] = copy_text

                    topic_id = db_utils.save_selected_topic(
                        track,
                        selected_topic["topic_title"],
                        selected_topic.get("core_angle", ""),
                        selected_topic.get("content_format", ""),
                    )
                    db_utils.save_generated_copy(
                        topic_id, selected_topic.get("content_format", ""), copy_text
                    )
                except Exception as e:
                    st.error(f"文案生成失败:{e}")

        copy_text = st.session_state.pipeline.get("copy_text")
        if copy_text:
            st.text_area("生成结果", value=copy_text, height=400)
