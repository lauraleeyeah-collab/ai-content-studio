"""
笔记爆款分析 — 7维度评分诊断单篇笔记爆款潜力
支持截图上传(自动识别内容)、笔记链接、文本粘贴三种输入方式
"""
import json
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.note_scorer import score_single_note
from agents.image_extractor import extract_from_images
from database import db_utils
from utils.ui_components import (
    inject_custom_css,
    render_grade_badge,
    render_score_bar,
    render_dimension_card,
    render_radar_chart,
    render_priority_list,
    DIMENSION_LABELS,
)
from utils.ui_components import render_api_key_input
from utils.demo_data import render_demo_toggle

st.set_page_config(page_title="笔记爆款分析", layout="wide")
inject_custom_css()

# ── 初始化 ──
db_utils.init_db()

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "analysis_note_data" not in st.session_state:
    st.session_state.analysis_note_data = None

# ── 侧栏 ──
with st.sidebar:
    st.markdown('<div class="sidebar-header">基础配置</div>', unsafe_allow_html=True)
    render_demo_toggle()
    render_api_key_input()
    track = st.text_input("赛道关键词", value="AI工具/自我提升")
    persona_description = st.text_area("账号人设描述(可选)", value="", height=100,
                                       placeholder="描述你的账号定位、目标人群和内容方向...")

# ── 页面标题 ──
st.markdown(
    '<div class="page-header"><h1>笔记爆款分析</h1>'
    '<p>输入一篇小红书笔记,从7个维度进行专业评分,雷达图可视化,精准定位改进方向</p></div>',
    unsafe_allow_html=True,
)

# ── 输入方式选择 ──
st.subheader("输入笔记信息")

input_mode = st.radio(
    "选择输入方式",
    ["截图上传", "笔记链接", "手动填写"],
    horizontal=True,
    key="note_score_input_mode",
)

# 截图上传 → 自动识别 → 预填表单
if input_mode == "截图上传":
    st.caption("支持三种方式添加截图: Cmd+V 粘贴 / 拖拽图片 / 点击选择文件")

    from utils.paste_capture import render_paste_zone, images_to_vision_input

    captured_images = render_paste_zone(key_prefix="note_score_paste")

    with st.expander("封面图(可选,用于封面评分)"):
        cover_file = st.file_uploader(
            "上传封面图",
            type=["png", "jpg", "jpeg", "webp"],
            key="note_score_cover_upload",
        )

    if captured_images:
        if st.button("从截图识别笔记信息", key="btn_extract_note_score", type="primary"):
            images_bytes = images_to_vision_input(captured_images)
            with st.spinner(f"AI正在识别{len(images_bytes)}张截图..."):
                try:
                    extracted = extract_from_images(track, images_bytes)
                    if extracted:
                        note = extracted[0]
                        st.session_state["note_score_prefill"] = note
                        if cover_file:
                            st.session_state["note_score_cover_bytes"] = [
                                {"bytes": cover_file.getvalue(), "mime": cover_file.type or "image/png"}
                            ]
                        st.success("识别成功! 请检查下方预填信息。")
                        st.rerun()
                except Exception as e:
                    st.error(f"识别失败: {e}")

# 笔记链接 → 自动提取
elif input_mode == "笔记链接":
    st.caption("输入小红书笔记链接,自动提取内容(部分链接可能因反爬限制无法访问)")
    url_input = st.text_input("笔记链接", placeholder="https://www.xiaohongshu.com/explore/...",
                              key="note_score_url")
    cover_url = st.text_input("封面图链接(可选)", placeholder="https://...", key="note_score_cover_url")

    if url_input:
        if st.button("从链接提取笔记信息", key="btn_extract_note_url", type="primary"):
            from agents.image_extractor import extract_from_url
            with st.spinner("正在从链接提取..."):
                try:
                    extracted = extract_from_url(track, url_input)
                    if extracted:
                        st.session_state["note_score_prefill"] = extracted[0]
                        if cover_url:
                            st.session_state["note_score_cover_url"] = cover_url
                        st.success("提取成功! 请检查下方预填信息。")
                        st.rerun()
                except Exception as e:
                    st.error(f"提取失败: {e}")

# 预填数据
prefill = st.session_state.get("note_score_prefill", {})

# ── 表单(支持预填 + 手动输入) ──
with st.form("note_score_form"):
    title_input = st.text_input(
        "笔记标题",
        value=prefill.get("title", ""),
        placeholder="输入小红书笔记的标题...",
    )
    body_text_input = st.text_area(
        "正文内容",
        height=200,
        value=prefill.get("body_text", ""),
        placeholder="粘贴笔记的正文文字...",
    )

    # 标签:预填或手动输入
    prefill_tags = prefill.get("hashtags", [])
    if isinstance(prefill_tags, list):
        prefill_tags_str = ", ".join(prefill_tags)
    else:
        prefill_tags_str = str(prefill_tags) if prefill_tags else ""
    hashtags_input = st.text_input(
        "标签(逗号分隔)",
        value=prefill_tags_str,
        placeholder="AI工具, 效率提升, 自我成长",
    )

    col1, col2 = st.columns(2)
    with col1:
        likes_input = st.number_input("点赞数", min_value=0,
                                      value=int(prefill.get("likes") or 0), step=1)
        collects_input = st.number_input("收藏数", min_value=0,
                                         value=int(prefill.get("collects") or 0), step=1)
    with col2:
        comments_input = st.number_input("评论数", min_value=0,
                                         value=int(prefill.get("comments") or 0), step=1)
        shares_input = st.number_input("分享数", min_value=0,
                                       value=int(prefill.get("shares") or 0), step=1)

    # 笔记类型
    prefill_type = prefill.get("note_type", "图文笔记")
    type_options = ["图文笔记", "视频笔记", "未知"]
    type_index = type_options.index(prefill_type) if prefill_type in type_options else 0
    note_type_input = st.selectbox("笔记类型", type_options, index=type_index)

    # 封面: 支持图片上传 + 文字描述
    with st.expander("封面信息(可选)"):
        cover_file_form = st.file_uploader(
            "上传封面图",
            type=["png", "jpg", "jpeg", "webp"],
            key="note_score_cover_form",
        )
        cover_desc_input = st.text_area(
            "或文字描述封面",
            height=100,
            value=prefill.get("cover_description") or "",
            placeholder="描述封面的视觉设计,如: 左侧产品图右侧大字标题,背景为浅黄色...",
        )

    submitted = st.form_submit_button("开始分析", type="primary", width="stretch")

# 清除预填缓存的按钮
if prefill:
    if st.button("清除预填数据", key="btn_clear_prefill"):
        st.session_state.pop("note_score_prefill", None)
        st.session_state.pop("note_score_cover_bytes", None)
        st.session_state.pop("note_score_cover_url", None)
        st.rerun()

# ── 分析执行 ──
if submitted:
    if not title_input.strip():
        st.warning("请输入笔记标题。")
    else:
        # 处理封面描述
        cover_desc = cover_desc_input.strip() if cover_desc_input.strip() else None
        if not cover_desc and prefill.get("cover_description"):
            cover_desc = prefill["cover_description"]

        note_data = {
            "title": title_input.strip(),
            "body_text": body_text_input.strip(),
            "hashtags": [t.strip() for t in hashtags_input.split(",") if t.strip()],
            "likes": int(likes_input),
            "comments": int(comments_input),
            "collects": int(collects_input),
            "shares": int(shares_input),
            "note_type": note_type_input,
            "cover_description": cover_desc,
        }

        with st.spinner("正在分析笔记,请稍候..."):
            try:
                result = score_single_note(
                    track=track,
                    note_data=note_data,
                    persona_description=persona_description if persona_description.strip() else None,
                )
                st.session_state.analysis_result = result
                st.session_state.analysis_note_data = note_data
                st.success("分析完成!")
            except Exception as e:
                st.error(f"分析失败: {e}")

# ── 结果展示 ──
result = st.session_state.analysis_result
note_data = st.session_state.analysis_note_data

if result:
    st.markdown("---")
    st.subheader("分析结果")

    scores = result.get("scores", {})
    total_score = result.get("total_score", 0)
    grade = result.get("grade", "C")
    improvement_priorities = result.get("improvement_priorities", [])

    # Row 1: 等级徽章 + 雷达图
    col_badge, col_radar = st.columns([1, 2])
    with col_badge:
        render_grade_badge(grade, total_score)

    with col_radar:
        scores_for_radar = {}
        for dim_key, dim_data in scores.items():
            if isinstance(dim_data, dict) and dim_data.get("score") is not None:
                scores_for_radar[dim_key] = dim_data["score"]
        fig = render_radar_chart(scores_for_radar, title="七维度评分雷达图")
        if fig is not None:
            st.plotly_chart(fig, width="stretch")

    st.markdown("---")

    # Row 2: 维度卡片
    st.subheader("维度详情")
    dim_keys = list(DIMENSION_LABELS.keys())
    for i in range(0, len(dim_keys), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            idx = i + j
            if idx < len(dim_keys):
                dk = dim_keys[idx]
                if dk in scores:
                    with cols[j]:
                        render_dimension_card(dk, scores[dk])
                        if scores[dk].get("score") is not None:
                            render_score_bar(DIMENSION_LABELS.get(dk, dk), scores[dk]["score"])

    st.markdown("---")

    # Row 3: 改进优先级
    st.subheader("优先改进方向")
    st.markdown("以下是得分最低的3个维度,建议优先从这些方向优化:")
    render_priority_list(improvement_priorities)

    # 保存按钮
    st.markdown("---")
    if st.button("保存本次分析", key="btn_save_analysis", width="stretch"):
        try:
            scores_json = json.dumps(scores, ensure_ascii=False)
            raw_input_json = json.dumps(note_data, ensure_ascii=False)
            db_utils.save_note_analysis(
                track=track,
                note_title=note_data.get("title", ""),
                note_type=note_data.get("note_type", ""),
                scores_json=scores_json,
                total_score=total_score,
                grade=grade,
                improvement_priorities=json.dumps(improvement_priorities, ensure_ascii=False),
                raw_input_json=raw_input_json,
            )
            st.success("已保存到数据库!")
        except Exception as e:
            st.error(f"保存失败: {e}")

# ── 历史记录 ──
st.markdown("---")
st.subheader("历史分析记录")

try:
    history = db_utils.get_note_analyses(track=track, limit=20)
except Exception:
    history = []

if history:
    for h in history:
        with st.expander(f"[{h['grade']} {h['total_score']}分] {h['note_title']}  ({h['created_at'][:16]})"):
            st.text(f"类型: {h['note_type']}")
            try:
                hist_scores = json.loads(h["scores_json"])
                for dk, dd in hist_scores.items():
                    if isinstance(dd, dict):
                        label = DIMENSION_LABELS.get(dk, dk)
                        st.text(f"  {label}: {dd.get('score', '?')}/10 - {dd.get('reason', '')}")
            except (json.JSONDecodeError, TypeError):
                st.json(h)
else:
    st.info("暂无历史记录,完成一次分析并保存后将显示在这里。")
