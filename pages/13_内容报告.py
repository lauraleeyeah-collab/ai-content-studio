"""
内容报告（工作台延伸）— AI 超级自媒体工具

一键串联 M1 图文工厂 → M2 视频工厂 → M3 渠道中心的完整生产链路，
输出可交付的内容生产报告（Markdown），可直接用于作品集与面试演示。
"""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.content_report_builder import build_content_report
from database import db_utils
from utils.ui_components import inject_custom_css
from utils.demo_data import render_demo_toggle, DEMO_TOPIC

st.set_page_config(page_title="内容报告", layout="wide")
inject_custom_css()

db_utils.init_db()
db_utils.ensure_default_persona()

if "report" not in st.session_state:
    st.session_state.report = {}

_default_persona = db_utils.get_default_persona()
DEFAULT_PERSONA = _default_persona["persona_description"] if _default_persona else ""

rp = st.session_state.report

st.markdown(
    '<div class="page-header"><h1>内容报告</h1>'
    "<p>一个选题 → 搜索词/标题/封面/正文/互动/分镜/播放优化/多平台版本/合规 → 完整生产报告</p></div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown('<div class="sidebar-header">内容报告</div>', unsafe_allow_html=True)
    demo_on = render_demo_toggle()
    api_key_input = st.text_input(
        "DashScope API Key", type="password",
        value=os.environ.get("DASHSCOPE_API_KEY", ""),
        help="在阿里云百炼/DashScope控制台获取。",
    )
    if api_key_input:
        os.environ["DASHSCOPE_API_KEY"] = api_key_input
    track = st.text_input("赛道关键词", value="AI工具/自我提升")
    persona_description = st.text_area("账号人设描述", value=DEFAULT_PERSONA, height=100)

if demo_on and not rp.get("topic"):
    if st.sidebar.button("一键填入示例选题", key="rp_fill_demo"):
        rp["topic"] = dict(DEMO_TOPIC)
        st.rerun()

topic = rp.get("topic", {})
t_title = st.text_input("选题标题", value=topic.get("title", ""), key="rp_title")
t_angle = st.text_area("选题角度", value=topic.get("angle", ""), height=70, key="rp_angle")
t_content = st.text_area("素材正文", value=topic.get("content", ""), height=140, key="rp_content")

channels = st.multiselect("覆盖渠道", ["小红书", "抖音", "视频号", "公众号", "知乎", "问一问"],
                          default=["小红书", "抖音", "视频号"], key="rp_channels")

if st.button("一键生成完整生产报告", key="btn_rp_build", type="primary"):
    if not t_title.strip():
        st.warning("请填写选题标题。")
    else:
        with st.spinner("正在串联 M1 图文 → M2 视频 → M3 渠道全流程..."):
            try:
                report = build_content_report(
                    track, t_title.strip(), t_angle.strip(), t_content.strip(),
                    persona_description, channels=channels,
                )
                rp["report"] = report
                rp["topic"] = {"title": t_title.strip(), "angle": t_angle.strip(), "content": t_content.strip()}
                db_utils.save_content_asset(
                    asset_type="report", channel="全渠道", title=t_title.strip(),
                    content=report["report_markdown"],
                    search_keywords="、".join(k.get("keyword", "") for k in report["search_keywords"][:3]),
                )
                st.success("生产报告已生成并保存到内容资产。")
            except Exception as e:
                st.error(f"报告生成失败：{e}")

report = rp.get("report")
if report:
    st.markdown("### 报告摘要")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("搜索词", len(report["search_keywords"]))
    with c2:
        passed = sum(1 for t in report["titles"] if t.get("keyword_check", {}).get("passed"))
        st.metric("标题通过关键词检查", f"{passed}/{len(report['titles'])}")
    with c3:
        st.metric("渠道版本", len(report["channel_versions"]))
    with c4:
        tl = report["script"].get("checks", {}).get("timeline", {})
        st.metric("分镜时间轴", "✅" if tl.get("passed") else "⚠️")

    st.markdown("### 关键产出")
    st.markdown(f"**搜索词 Top3：** " + " / ".join(f"`{k['keyword']}`" for k in report["search_keywords"][:3]))
    st.markdown(f"**5 秒钩子：** {report['play'].get('five_sec_hook', '')}")
    st.markdown(f"**合规结论：** " + "；".join(
        f"{ch} {'✅' if v['red_lines'].get('passed') else '⚠️'}" for ch, v in report["compliance"].items()
    ))

    st.markdown("### 下载与预览")
    st.download_button(
        "下载完整生产报告.md",
        data=report["report_markdown"],
        file_name=f"内容生产报告-{report['topic']['title'][:20]}.md",
        mime="text/markdown",
        key="btn_download_report",
    )
    with st.expander("预览完整报告"):
        st.text(report["report_markdown"])
