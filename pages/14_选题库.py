"""
选题库（增强）— AI 超级自媒体工具

内容资产池：选题入库/状态管理/搜索复用，一键跳转内容报告开始生产。
选题状态：idea 灵感 → in_progress 创作中 → done 已完成 → published 已发布。
"""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import db_utils
from utils.ui_components import inject_custom_css
from utils.demo_data import render_demo_toggle, DEMO_TOPIC

STATUS_LABELS = {
    "idea": "💡 灵感",
    "in_progress": "🛠 创作中",
    "done": "✅ 已完成",
    "published": "🚀 已发布",
}

st.set_page_config(page_title="选题库", layout="wide")
inject_custom_css()

db_utils.init_db()
db_utils.ensure_default_persona()

st.markdown(
    '<div class="page-header"><h1>选题库</h1>'
    "<p>内容资产池：选题入库 → 状态管理 → 一键开始生产，防止好点子流失</p></div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown('<div class="sidebar-header">选题库</div>', unsafe_allow_html=True)
    render_demo_toggle()

if st.sidebar.button("一键填入示例选题", key="lib_fill_demo"):
    db_utils.save_topic_to_library(
        track="AI工具/自我提升", title=DEMO_TOPIC["title"], angle=DEMO_TOPIC["angle"],
        content=DEMO_TOPIC["content"], status="idea",
    )
    st.rerun()

tab1, tab2 = st.tabs(["① 选题列表", "② 新增选题"])

# ══════════════ Tab 1: 选题列表 ══════════════
with tab1:
    st.subheader("选题列表")
    c1, c2 = st.columns([2, 3])
    with c1:
        status_filter = st.selectbox("按状态筛选", ["全部"] + list(STATUS_LABELS.values()), index=0, key="lib_status_filter")
    with c2:
        search_kw = st.text_input("搜索选题（标题/角度/内容）", value="", key="lib_search")

    if search_kw.strip():
        topics = db_utils.search_topic_library(search_kw.strip())
    else:
        topics = db_utils.get_topic_library()

    if status_filter != "全部":
        reverse_map = {v: k for k, v in STATUS_LABELS.items()}
        target = reverse_map.get(status_filter)
        topics = [t for t in topics if t.get("status") == target]

    if not topics:
        st.info("选题库为空。可在②新增选题，或用示例按钮快速体验。")
    else:
        st.caption(f"共 {len(topics)} 个选题")
        for t in topics:
            label = STATUS_LABELS.get(t.get("status"), t.get("status") or "idea")
            with st.container(border=True):
                st.markdown(f"**{t.get('title')}** ｜ {label}")
                angle = t.get("platform_review") or t.get("content") or ""
                st.caption(f"角度：{(angle or '-')[:80]}")
                st.caption(f"赛道：{t.get('channel') or '-'} ｜ 更新：{t.get('created_at') or '-'}")

                b1, b2, b3, b4, b5 = st.columns([1, 1, 1, 1, 1])
                with b1:
                    if t.get("status") != "in_progress" and st.button("开始创作", key=f"lib_start_{t['id']}"):
                        db_utils.update_asset_status(t["id"], "in_progress")
                        # 把选题带入内容报告页
                        st.session_state["report"] = {
                            "topic": {"title": t["title"], "angle": t.get("platform_review") or "", "content": t.get("content") or ""}
                        }
                        st.rerun()
                with b2:
                    if t.get("status") != "done" and st.button("标记完成", key=f"lib_done_{t['id']}"):
                        db_utils.update_asset_status(t["id"], "done")
                        st.rerun()
                with b3:
                    if t.get("status") != "published" and st.button("标记已发布", key=f"lib_pub_{t['id']}"):
                        db_utils.update_asset_status(t["id"], "published")
                        st.rerun()
                with b4:
                    if st.button("回到灵感", key=f"lib_idea_{t['id']}"):
                        db_utils.update_asset_status(t["id"], "idea")
                        st.rerun()
                with b5:
                    if st.button("删除", key=f"lib_del_{t['id']}"):
                        db_utils.delete_asset(t["id"])
                        st.rerun()

        if st.button("一键生成完整生产报告（从选中的最新选题）", key="lib_go_report"):
            if topics:
                latest = topics[0]
                st.session_state["report"] = {
                    "topic": {"title": latest["title"], "angle": latest.get("platform_review") or "", "content": latest.get("content") or ""}
                }
                st.success("已把选题带入「内容报告」，请切换到 13 内容报告 页面继续。")

# ══════════════ Tab 2: 新增选题 ══════════════
with tab2:
    st.subheader("新增选题")
    with st.form("lib_form"):
        lib_track = st.text_input("赛道", value="AI工具/自我提升")
        lib_title = st.text_input("选题标题", value="")
        lib_angle = st.text_area("选题角度", height=80, value="")
        lib_content = st.text_area("素材/大纲", height=140, value="")
        lib_status = st.selectbox("初始状态", ["idea", "in_progress", "done"], index=0)
        submitted = st.form_submit_button("加入选题库", type="primary")
        if submitted:
            if not lib_title.strip():
                st.warning("请填写选题标题。")
            else:
                aid = db_utils.save_topic_to_library(
                    track=lib_track.strip(), title=lib_title.strip(),
                    angle=lib_angle.strip(), content=lib_content.strip(), status=lib_status,
                )
                st.success(f"选题已加入选题库（ID {aid}）。")
                st.rerun()
