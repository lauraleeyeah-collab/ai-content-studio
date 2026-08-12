"""
批量生产（增强）— AI 超级自媒体工具

一次处理多个选题：从选题库多选或粘贴多行选题，每个选题完整跑一遍
M1 图文 → M2 视频 → M3 渠道生产链路，产出合并报告，单条失败不影响其他。
"""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.batch_production import batch_produce, parse_bulk_topics
from agents.content_report_builder import DEFAULT_CHANNELS
from database import db_utils
from utils.ui_components import inject_custom_css
from utils.demo_data import render_demo_toggle

DEMO_BULK_TOPICS = [
    {"title": "用AI写周报被领导点名表扬，我的3个提示词技巧", "angle": "真实使用记录视角", "content": "分享3个AI写周报的提示词技巧：给AI角色设定、喂结构化素材、追加追问。"},
    {"title": "DeepSeek+Excel，1分钟搞定月度数据汇总", "angle": "工具实操教程视角", "content": "演示用DeepSeek写公式+辅助数据分析的完整流程，不需要编程基础。"},
    {"title": "普通人和高薪的差距，就差这套AI工作流", "angle": "对比反差视角", "content": "对比普通人和高效职场人的AI工作流差异，给出可复用的提效组合。"},
]

st.set_page_config(page_title="批量生产", layout="wide")
inject_custom_css()

db_utils.init_db()
db_utils.ensure_default_persona()

if "batch" not in st.session_state:
    st.session_state.batch = {}

_default_persona = db_utils.get_default_persona()
DEFAULT_PERSONA = _default_persona["persona_description"] if _default_persona else ""

bt = st.session_state.batch

st.markdown(
    '<div class="page-header"><h1>批量生产</h1>'
    "<p>一次处理多个选题：每个选题完整跑 M1 图文 → M2 视频 → M3 渠道，单条失败不影响其他</p></div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown('<div class="sidebar-header">批量生产</div>', unsafe_allow_html=True)
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

if demo_on and not bt.get("topics"):
    if st.sidebar.button("一键填入批量示例选题", key="batch_fill_demo"):
        bt["topics"] = list(DEMO_BULK_TOPICS)
        st.session_state["batch_mode"] = "粘贴多行选题"
        st.session_state["batch_text"] = "\n".join(
            f"{t['title']}｜{t['angle']}｜{t['content']}" for t in DEMO_BULK_TOPICS
        )
        st.rerun()

tab1, tab2 = st.tabs(["① 选择选题", "② 批量执行与结果"])

# ══════════════ Tab 1: 选择选题 ══════════════
with tab1:
    st.subheader("选择选题")
    source_mode = st.radio("输入方式", ["从选题库多选", "粘贴多行选题"], horizontal=True, key="batch_mode")

    topics = []
    if source_mode == "从选题库多选":
        library = db_utils.get_topic_library()
        if not library:
            st.info("选题库为空。可先用示例按钮，或到「选题库」新增。")
        else:
            options = {f"[{t['status']}] {t['title']}": t for t in library}
            selected = st.multiselect("勾选选题（可多选）", list(options.keys()), key="batch_lib_select")
            topics = [options[k] for k in selected]
    else:
        bulk_text = st.text_area(
            "粘贴多行选题（每行一个；支持「标题｜角度｜素材」或「标题,角度,素材」）",
            height=200, key="batch_text",
        )
        if bulk_text.strip():
            topics = parse_bulk_topics(bulk_text)

    channels = st.multiselect("覆盖渠道", ["小红书", "抖音", "视频号", "公众号", "知乎", "问一问"],
                              default=list(DEFAULT_CHANNELS), key="batch_channels")

    st.markdown(f"**已选 {len(topics)} 个选题：**")
    for t in topics[:10]:
        st.markdown(f"- {t.get('title', '')}")

    if st.button("开始批量生产", key="btn_batch_start", type="primary"):
        if not topics:
            st.warning("请先选择或粘贴至少一个选题。")
        elif not channels:
            st.warning("请至少选择一个覆盖渠道。")
        else:
            st.session_state["batch_running"] = True
            st.session_state["batch_plan"] = {
                "topics": topics, "track": track, "persona": persona_description, "channels": channels
            }
            st.rerun()

# ══════════════ Tab 2: 批量执行与结果 ══════════════
with tab2:
    st.subheader("批量执行与结果")

    if st.session_state.get("batch_running") and st.session_state.get("batch_plan"):
        plan = st.session_state["batch_plan"]
        progress_bar = st.progress(0.0, text="准备批量生产...")
        status_text = st.empty()
        total = len(plan["topics"])

        def _cb(done, total_, title):
            progress_bar.progress(done / total_, text=f"正在生产 {done}/{total_}：{title}")

        try:
            result = batch_produce(
                plan["topics"], plan["track"], plan["persona"],
                channels=plan["channels"], progress_callback=_cb,
            )
            bt["result"] = result
            # 保存每条成功报告到内容资产
            saved = 0
            for r in result["results"]:
                if r["status"] == "success":
                    db_utils.save_content_asset(
                        asset_type="report", channel="全渠道", title=r["topic_title"],
                        content=r["report"]["report_markdown"],
                        search_keywords="、".join(k.get("keyword", "") for k in r["report"]["search_keywords"][:3]),
                    )
                    saved += 1
            bt["saved_count"] = saved
            bt["done_message"] = (
                f"批量生产完成：成功 {result['summary']['success']} / 失败 {result['summary']['failed']}，"
                f"报告已保存 {saved} 份。"
            )
            st.session_state["batch_running"] = False
        except Exception as e:
            st.session_state["batch_running"] = False
            st.error(f"批量生产失败：{e}")
        st.rerun()

    result = bt.get("result")
    if result:
        if bt.get("done_message"):
            st.success(bt["done_message"])
        summary = result["summary"]
        st.markdown("### 汇总")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("选题数", summary["total"])
        with c2:
            st.metric("成功", summary["success"])
        with c3:
            st.metric("渠道版本合计", summary["total_channel_versions"])
        with c4:
            st.metric("搜索词合计", summary["total_keywords"])

        st.markdown("### 每条生产结果")
        rows = []
        for r in result["results"]:
            if r["status"] == "success":
                rep = r["report"]
                rows.append({
                    "选题": r["topic_title"], "状态": "✅",
                    "耗时ms": r["duration_ms"],
                    "搜索词": len(rep.get("search_keywords", [])),
                    "渠道版本": len(rep.get("channel_versions", [])),
                    "报告字数": len(rep.get("report_markdown", "")),
                })
            else:
                rows.append({"选题": r["topic_title"], "状态": "❌", "耗时ms": "-",
                             "搜索词": "-", "渠道版本": "-", "报告字数": f"错误：{r.get('error', '')[:30]}"})
        st.dataframe(rows, use_container_width=True)

        st.markdown("### 导出")
        st.download_button(
            "下载合并生产报告.md",
            data=result["combined_markdown"],
            file_name=f"批量生产报告-{summary['success']}选题.md",
            mime="text/markdown",
            key="btn_batch_download",
        )
        with st.expander("预览合并报告开头"):
            st.text(result["combined_markdown"][:1500])

        if st.button("清空结果", key="btn_batch_clear"):
            st.session_state.pop("batch", None)
            st.rerun()
