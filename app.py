"""
AI 超级自媒体工具 — 工作台首页

主入口：全渠道概览 + 快速统计 + 功能模块导航 + 最近活动。
覆盖：图文工厂 / 视频工厂 / 渠道中心 / 数据中心 / 账号中心 / 内容日历 / 内容报告。
"""
import os
import logging
import sys

import streamlit as st

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

sys.path.insert(0, os.path.dirname(__file__))

from database import db_utils
from utils.ui_components import inject_custom_css, render_metric_card, render_api_key_input
from utils.demo_data import render_demo_toggle

st.set_page_config(page_title="AI 超级自媒体工具", layout="wide", page_icon="")
inject_custom_css()

# ── 初始化 ──
db_utils.init_db()
db_utils.init_channels()
db_utils.ensure_default_persona()
if "pipeline" not in st.session_state:
    st.session_state.pipeline = {}

_default_persona = db_utils.get_default_persona()
DEFAULT_PERSONA = _default_persona["persona_description"] if _default_persona else ""

# ── 侧栏全局配置 ──
with st.sidebar:
    st.markdown('<div class="sidebar-header">全局配置</div>', unsafe_allow_html=True)
    demo_on = render_demo_toggle()
    render_api_key_input()

    track = st.text_input("赛道关键词", value="AI工具/自我提升")
    persona_options = [(p["name"], p["persona_description"]) for p in db_utils.get_personas()] or [("默认", DEFAULT_PERSONA)]
    persona_name = st.selectbox("当前账号人设", [n for n, _ in persona_options], index=0, key="app_persona")
    persona_description = st.text_area("账号人设描述", value=DEFAULT_PERSONA, height=140)
    if persona_name:
        matched = next((d for n, d in persona_options if n == persona_name), DEFAULT_PERSONA)
        if matched != persona_description:
            persona_description = matched

# ── 页面标题 ──
st.markdown(
    '<div class="page-header">'
    "<h1>AI 超级自媒体工具</h1>"
    "<p>按平台切分工作台：小红书 / 公众号 / 知乎 各自独立生产 · 一次生产，多平台适配，数据反哺</p>"
    "</div>",
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
    render_metric_card("内容资产", stats.get("content_assets_count", 0), icon="")
with col2:
    render_metric_card("渠道改写", stats.get("channel_rewrites_count", 0), icon="")
with col3:
    render_metric_card("发布记录", stats.get("publish_records_count", 0), icon="")
with col4:
    render_metric_card("搜索词库", stats.get("search_keywords_count", 0), icon="")

st.html('<div class="spacer"></div>')

col5, col6, col7, col8 = st.columns(4)
with col5:
    render_metric_card("笔记分析", stats.get("note_analyses_count", 0), icon="")
with col6:
    render_metric_card("竞品账号", stats.get("competitor_accounts_count", 0), icon="")
with col7:
    render_metric_card("生成选题", stats.get("topics_generated_count", 0), icon="")
with col8:
    render_metric_card("生成文案", stats.get("copies_generated_count", 0), icon="")

st.html('<div class="spacer"></div>')

# ── 全渠道概览 ──
st.subheader("全渠道概览")
summary = db_utils.get_channel_summary()
channels = db_utils.get_channels()
if summary:
    by_name = {s["channel"]: s for s in summary}
    cols = st.columns(len(channels))
    for col, ch in zip(cols, channels):
        s = by_name.get(ch["name"])
        with col:
            if s:
                st.metric(
                    ch["name"],
                    f"{s['total_views']:,}" if s["total_views"] else "0",
                    f"收藏率 {s['collect_rate']:.1%}",
                )
                st.caption(f"发布 {s['post_count']} 条 ｜ 互动率 {s['interaction_rate']:.1%}")
            else:
                st.metric(ch["name"], "0", "暂无数据")
                st.caption("去数据中心回填数据")
else:
    st.info("暂无渠道数据。在「数据中心」回填发布数据后，这里会显示 6 个平台的曝光与收藏率概览。")

st.html('<div class="spacer"></div>')

# ── 发布计划 ──
st.subheader("最近发布计划")
schedules = db_utils.get_schedules(limit=5)
if schedules:
    for s in schedules:
        icon = {"planned": "⏳", "published": "✅", "skipped": "➖"}.get(s.get("status"), "⏳")
        st.text(
            f"{icon} {s.get('planned_date')} {s.get('planned_time')} ｜ {s.get('channel')} ｜ "
            f"{s.get('content_title') or '(无标题)'}"
        )
else:
    st.caption("暂无发布计划。在「内容日历」或「渠道中心」生成发布清单后自动加入。")

st.html('<div class="spacer"></div>')

# ── 平台工作台（按社交媒体切分）──
st.subheader("平台工作台（按社交媒体切分）")

platform_modules = [
    ("pages/13_内容报告.py", "小红书工作台", "选题/标题/封面/正文/互动 + 视频分镜 + 多平台版本"),
    ("pages/16_公众号工作台.py", "公众号工作台", "选题角度/标题/头图/深度长文/在看与留言互动"),
    ("pages/17_知乎工作台.py", "知乎工作台", "选题角度/标题/头图/回答正文/赞同与收藏互动"),
]
cols = st.columns(3)
for col, (path, title, desc) in zip(cols, platform_modules):
    with col:
        st.markdown(
            f'<div class="action-card"><div class="action-icon"></div>'
            f'<div class="action-title">{title}</div>'
            f'<div class="action-desc">{desc}</div></div>',
            unsafe_allow_html=True,
        )
        st.page_link(path, label=f"进入{title} →")

st.html('<div class="spacer"></div>')

# ── 功能入口 ──
st.subheader("核心生产模块")

core_modules = [
    ("pages/7_图文工厂.py", "图文工厂", "选题 → 搜索词 → 标题 → 封面 → 正文 → 互动话术"),
    ("pages/8_视频工厂.py", "视频工厂", "秒级分镜 → 播放优化 → 视频生成提示词导出"),
    ("pages/9_渠道中心.py", "渠道中心", "6 平台规则库 → 一键改写 → 合规检查 → 发布清单"),
    ("pages/10_数据中心.py", "数据中心", "数据回填 → 渠道对比 → 爆款归因 → 历史管理"),
    ("pages/13_内容报告.py", "内容报告", "一键生成完整生产报告，可直接用于作品集"),
]
cols = st.columns(5)
for col, (path, title, desc) in zip(cols, core_modules):
    with col:
        st.markdown(
            f'<div class="action-card"><div class="action-icon"></div>'
            f'<div class="action-title">{title}</div>'
            f'<div class="action-desc">{desc}</div></div>',
            unsafe_allow_html=True,
        )
        st.page_link(path, label=f"进入{title} →")

st.html('<div class="spacer"></div>')

# ── 运营与辅助模块 ──
st.subheader("运营与辅助模块")

aux_modules = [
    ("pages/1_热点选题流水线.py", "热点选题流水线", "5步AI流水线：采集→筛选→拆解→选题→文案"),
    ("pages/2_笔记爆款分析.py", "笔记爆款分析", "7维度评分诊断，雷达图可视化"),
    ("pages/3_竞品账号分析.py", "竞品账号分析", "竞品策略/发布规律/互动数据深挖"),
    ("pages/4_热门内容趋势.py", "热门内容趋势", "标签共现图谱 + 内容空白发现"),
    ("pages/5_内容创作辅助.py", "内容创作辅助", "标题优化 / A/B测试 / 标签推荐"),
    ("pages/11_账号中心.py", "账号中心", "多账号人设库，切换默认账号"),
    ("pages/12_内容日历.py", "内容日历", "发布计划周视图 + 平台分布"),
    ("pages/6_历史记录管理.py", "历史记录管理", "全部历史数据的查看/复用/删除"),
]
cols = st.columns(4)
for idx, (path, title, desc) in enumerate(aux_modules):
    with cols[idx % 4]:
        st.markdown(
            f'<div class="action-card"><div class="action-icon"></div>'
            f'<div class="action-title">{title}</div>'
            f'<div class="action-desc">{desc}</div></div>',
            unsafe_allow_html=True,
        )
        st.page_link(path, label=f"进入{title} →")

# ── 最近活动 ──
st.html('<div class="spacer"></div>')
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
