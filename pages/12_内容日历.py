"""
内容日历（P1）— AI 超级自媒体工具

发布计划视图（周视图 + 平台分布）：规划一周内各平台发布时间，
与渠道中心发布清单打通（生成清单时可同步加入日历）。
"""
import os
import sys
from collections import Counter, defaultdict

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import db_utils
from utils.ui_components import inject_custom_css
from utils.demo_data import render_demo_toggle

st.set_page_config(page_title="内容日历", layout="wide")
inject_custom_css()

db_utils.init_db()
db_utils.init_channels()

st.markdown(
    '<div class="page-header"><h1>内容日历</h1>'
    "<p>发布计划周视图 + 平台分布，与渠道中心发布清单打通</p></div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown('<div class="sidebar-header">内容日历</div>', unsafe_allow_html=True)
    render_demo_toggle()

tab1, tab2 = st.tabs(["① 周视图", "② 新增发布计划"])

schedules = db_utils.get_schedules()

# ══════════════ Tab 1: 周视图 ══════════════
with tab1:
    st.subheader("发布计划周视图")
    if not schedules:
        st.info("暂无发布计划。可在②新增，或在渠道中心生成发布清单时同步加入日历。")
    else:
        # 按日期分组
        by_date = defaultdict(list)
        for s in schedules:
            by_date[s.get("planned_date") or "未排期"].append(s)

        status_icon = {"planned": "⏳", "published": "✅", "skipped": "➖"}
        for date in sorted(by_date.keys()):
            items = by_date[date]
            with st.expander(f"📅 {date}（{len(items)} 条）", expanded=False):
                for s in items:
                    icon = status_icon.get(s.get("status", "planned"), "⏳")
                    st.markdown(
                        f"{icon} **{s.get('content_title') or '(无标题)'}** "
                        f"｜ {s.get('channel') or '-'} ｜ {s.get('planned_time') or '--:--'} ｜ "
                        f"人设：{s.get('persona_name') or '-'}"
                    )
                    b1, b2, b3 = st.columns(3)
                    with b1:
                        if st.button("标记已发布", key=f"pub_{s['id']}"):
                            db_utils.update_schedule_status(s["id"], "published")
                            st.rerun()
                    with b2:
                        if st.button("跳过", key=f"skip_{s['id']}"):
                            db_utils.update_schedule_status(s["id"], "skipped")
                            st.rerun()
                    with b3:
                        if st.button("删除", key=f"del_sched_{s['id']}"):
                            db_utils.delete_schedule(s["id"])
                            st.rerun()
                    st.markdown("---")

        # 平台分布
        st.subheader("平台分布")
        channel_counter = Counter(s.get("channel") or "未指定" for s in schedules)
        status_counter = Counter(s.get("status") or "planned" for s in schedules)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**按平台：**")
            for ch, cnt in channel_counter.most_common():
                st.markdown(f"- {ch}：{cnt} 条")
        with c2:
            st.markdown("**按状态：**")
            for stt, cnt in status_counter.most_common():
                st.markdown(f"- {stt}：{cnt} 条")

# ══════════════ Tab 2: 新增发布计划 ══════════════
with tab2:
    st.subheader("新增发布计划")
    channels = [c["name"] for c in db_utils.get_channels()]
    personas = db_utils.get_personas()

    with st.form("schedule_form"):
        s_title = st.text_input("内容标题", value="")
        s_channel = st.selectbox("渠道", channels or ["小红书", "抖音", "视频号", "公众号", "知乎", "问一问"])
        s_date = st.text_input("计划日期（YYYY-MM-DD）", value="2026-08-13")
        s_time = st.text_input("计划时间（HH:MM）", value="20:00")
        s_persona = st.selectbox("账号人设", [p["name"] for p in personas] or ["默认"]) if personas else None
        s_notes = st.text_input("备注", value="")
        submitted = st.form_submit_button("加入日历", type="primary")
        if submitted:
            if not s_title.strip():
                st.warning("请填写内容标题。")
            else:
                sid = db_utils.save_schedule(
                    asset_id=0, channel=s_channel, content_title=s_title.strip(),
                    planned_date=s_date.strip(), planned_time=s_time.strip(),
                    persona_name=s_persona or "", notes=s_notes.strip(),
                )
                st.success(f"发布计划已加入日历（ID {sid}）。")
                st.rerun()
