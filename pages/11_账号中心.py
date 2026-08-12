"""
账号中心（P1）— AI 超级自媒体工具

多账号人设库：账号档案（名称/领域/语气/平台绑定/人设描述），
支持切换默认账号，图文/视频/渠道工厂自动使用当前账号人设生成。
"""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import db_utils
from utils.ui_components import inject_custom_css
from utils.demo_data import render_demo_toggle

DEFAULT_SEED_PERSONA = (
    "人设:深圳搞钱女孩,定位是借助AI工具辅助工作效率和个人成长,内容覆盖英语学习、阅读、"
    "职场发展、理财、搞钱副业、自律习惯六个方向,内容配比为干货80%+情绪20%。"
    "目标人群:大学生和职场人士,核心诉求是用AI实现自我提升和收入增长。"
)

st.set_page_config(page_title="账号中心", layout="wide")
inject_custom_css()

db_utils.init_db()

# 预置默认人设（首次使用）
if not db_utils.get_personas():
    db_utils.save_persona(
        name="深圳搞钱女孩", domain="AI工具/自我提升", tone="干货80%+情绪20%",
        channels="小红书,抖音,视频号", persona_description=DEFAULT_SEED_PERSONA, style_guide_ref="style_samples/style_guide_v2.md",
    )
    db_utils.set_default_persona(db_utils.get_personas()[0]["id"])

st.markdown(
    '<div class="page-header"><h1>账号中心</h1>'
    "<p>多账号人设库：切换当前账号后，图文/视频/渠道工厂自动按该人设生成内容</p></div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown('<div class="sidebar-header">账号中心</div>', unsafe_allow_html=True)
    render_demo_toggle()

personas = db_utils.get_personas()
default = db_utils.get_default_persona()

st.markdown(f"**当前默认账号：** {'`' + default['name'] + '`' if default else '（未设置）'}")

col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("账号列表")
    for p in personas:
        is_def = p.get("is_default")
        with st.container(border=True):
            tag = " ⭐ 当前账号" if is_def else ""
            st.markdown(f"**{p.get('name', '未命名')}**{tag}")
            st.caption(
                f"领域：{p.get('domain') or '-'} ｜ 语气：{p.get('tone') or '-'} ｜ "
                f"平台：{p.get('channels') or '-'} ｜ 风格参考：{p.get('style_guide_ref') or '-'}"
            )
            st.markdown(f"{p.get('persona_description') or ''[:120]}...")
            b1, b2, b3 = st.columns(3)
            with b1:
                if not is_def and st.button("设为当前", key=f"set_def_{p['id']}"):
                    db_utils.set_default_persona(p["id"])
                    st.rerun()
            with b2:
                if st.button("删除", key=f"del_persona_{p['id']}"):
                    db_utils.delete_persona(p["id"])
                    st.rerun()
            with b3:
                st.caption(f"ID {p['id']}")

with col2:
    st.subheader("新增账号")
    with st.form("persona_form"):
        p_name = st.text_input("账号名称", value="")
        p_domain = st.text_input("领域", value="AI工具/自我提升")
        p_tone = st.text_input("语气", value="干货80%+情绪20%")
        p_channels = st.text_input("绑定平台（逗号分隔）", value="小红书,抖音,视频号")
        p_ref = st.text_input("风格参考文件", value="style_samples/style_guide_v2.md")
        p_desc = st.text_area("人设描述", height=180, value="")
        submitted = st.form_submit_button("保存账号", type="primary")
        if submitted:
            if not p_name.strip():
                st.warning("请填写账号名称。")
            else:
                pid = db_utils.save_persona(
                    name=p_name.strip(), domain=p_domain.strip(), tone=p_tone.strip(),
                    channels=p_channels.strip(), style_guide_ref=p_ref.strip(),
                    persona_description=p_desc.strip(),
                )
                st.success(f"账号「{p_name.strip()}」已保存（ID {pid}）。")
                st.rerun()
