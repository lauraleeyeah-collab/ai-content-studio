"""
小红书内容创作工作台 — Dashboard 着陆页

多功能工具的主入口,提供:
- 快速统计概览
- 功能模块入口导航
- 最近活动记录
"""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from database import db_utils
from utils.ui_components import inject_custom_css, render_metric_card
from utils.demo_data import render_demo_toggle

DEFAULT_PERSONA = (
    "人设:深圳搞钱女孩,定位是借助AI工具辅助工作效率和个人成长,内容覆盖英语学习、阅读、"
    "职场发展、理财、搞钱副业、自律习惯六个方向,内容配比为干货80%+情绪20%。"
    "目标人群:大学生和职场人士,核心诉求是用AI实现自我提升和收入增长。"
)

st.set_page_config(page_title="小红书内容创作工作台", layout="wide", page_icon="")
inject_custom_css()

# ── 初始化 ──
db_utils.init_db()
if "pipeline" not in st.session_state:
    st.session_state.pipeline = {}

# ── 侧栏全局配置 ──
with st.sidebar:
    st.markdown('<div class="sidebar-header">全局配置</div>', unsafe_allow_html=True)
    demo_on = render_demo_toggle()
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

# ── 页面标题 ──
st.markdown(
    '<div class="page-header">'
    '<h1>小红书内容创作工作台</h1>'
    '<p>AI 驱动的内容分析、竞品研究与爆款创作全流程工具</p>'
    '</div>',
    unsafe_allow_html=True,
)

if st.session_state.get("demo_mode"):
    st.info(
        "当前为演示模式：所有 AI 调用返回内置示例结果。"
        "关闭侧栏的「演示模式」开关并填入真实 API Key 即可切换到真实调用。"
    )

# ── 快速统计 ──
stats = db_utils.get_dashboard_stats()

col1, col2, col3, col4 = st.columns(4)
with col1:
    render_metric_card("笔记分析", stats.get("note_analyses_count", 0), icon="")
with col2:
    render_metric_card("竞品账号", stats.get("competitor_accounts_count", 0), icon="")
with col3:
    render_metric_card("生成选题", stats.get("topics_generated_count", 0), icon="")
with col4:
    render_metric_card("生成文案", stats.get("copies_generated_count", 0), icon="")

st.markdown("<br>", unsafe_allow_html=True)

# ── 功能入口 ──
st.subheader("功能模块")

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        '<div class="action-card">'
        '<div class="action-icon"></div>'
        '<div class="action-title">热点选题流水线</div>'
        '<div class="action-desc">5步AI流水线:采集 → 筛选 → 拆解 → 选题 → 文案,全流程可视化</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/1_热点选题流水线.py", label="进入热点选题流水线 →")

    st.markdown(
        '<div class="action-card">'
        '<div class="action-icon"></div>'
        '<div class="action-title">竞品账号分析</div>'
        '<div class="action-desc">深度分析竞品内容策略、发布规律、互动数据,提炼可借鉴套路</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/3_竞品账号分析.py", label="进入竞品账号分析 →")

with col2:
    st.markdown(
        '<div class="action-card">'
        '<div class="action-icon"></div>'
        '<div class="action-title">笔记爆款分析</div>'
        '<div class="action-desc">7维度评分诊断单篇笔记爆款潜力,雷达图可视化,精准定位改进方向</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/2_笔记爆款分析.py", label="进入笔记爆款分析 →")

    st.markdown(
        '<div class="action-card">'
        '<div class="action-icon"></div>'
        '<div class="action-title">热门内容趋势</div>'
        '<div class="action-desc">品类级趋势分析,标签共现图谱,发现内容空白与爆款规律</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/4_热门内容趋势.py", label="进入热门内容趋势 →")

st.markdown("<br>", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    st.markdown(
        '<div class="action-card">'
        '<div class="action-icon"></div>'
        '<div class="action-title">内容创作辅助</div>'
        '<div class="action-desc">标题优化、A/B测试、标签推荐、文案诊断,全方位提升内容质量</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/5_内容创作辅助.py", label="进入内容创作辅助 →")

with col2:
    st.markdown(
        '<div class="action-card">'
        '<div class="action-icon"></div>'
        '<div class="action-title">历史记录管理</div>'
        '<div class="action-desc">查看、复用或删除全部历史数据，让每次分析沉淀为账号运营资产</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/6_历史记录管理.py", label="进入历史记录管理 →")


# ── 最近活动 ──
st.markdown("<br>", unsafe_allow_html=True)
st.subheader("最近活动")

activities = db_utils.get_recent_activities(limit=10)

TYPE_LABELS = {
    "note_analysis": "笔记分析",
    "topic": "选题生成",
    "copy": "文案生成",
    "trend": "趋势分析",
}

if activities:
    for act in activities:
        type_label = TYPE_LABELS.get(act.get("type", ""), act.get("type", ""))
        st.text(f"[{act.get('created_at', '')[:16]}] {type_label}: {act.get('title', '')} {act.get('detail', '')}")
else:
    st.info("暂无活动记录。开始使用各功能模块后,这里会显示最近的操作。")
