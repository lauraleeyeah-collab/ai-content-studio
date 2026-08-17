"""
平台工作台共享 UI（公众号 / 知乎 / 小红书工作台页面复用）。

一个平台一个页面，页面只传平台名进来；渲染逻辑、入库、下载全部收敛在这里，
避免多页面重复代码，也方便后续新增平台（如抖音、视频号工作台）。
"""
import streamlit as st

from agents.platform_workshop import produce_for_platform
from database import db_utils
from utils.demo_data import render_demo_toggle

DEMO_WORKSHOP_TOPIC = {
    "title": "用AI写周报被领导点名表扬",
    "angle": "真实使用记录视角",
    "content": "分享3个AI写周报的提示词技巧：给AI角色设定、喂结构化素材、追加追问。",
}


def render_platform_workshop(platform: str) -> None:
    """渲染指定平台的工作台页面。"""
    st.set_page_config(page_title=f"{platform}工作台", layout="wide")

    from utils.ui_components import inject_custom_css, render_api_key_input
    inject_custom_css()
    db_utils.init_db()
    db_utils.ensure_default_persona()

    key = f"ws_{platform}"
    if key not in st.session_state:
        st.session_state[key] = {}
    ws = st.session_state[key]

    _default_persona = db_utils.get_default_persona()
    DEFAULT_PERSONA = _default_persona["persona_description"] if _default_persona else ""

    st.markdown(
        f'<div class="page-header"><h1>{platform}工作台</h1>'
        f"<p>平台专属生产：选题角度 → 标题 → 封面 → 正文 → 互动（收藏/转发/评论）→ 报告入库</p></div>",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown(f'<div class="sidebar-header">{platform}工作台</div>', unsafe_allow_html=True)
        demo_on = render_demo_toggle()
        render_api_key_input()
        track = st.text_input("赛道关键词", value="AI工具/自我提升")
        persona_description = st.text_area("账号人设描述", value=DEFAULT_PERSONA, height=100)

    if demo_on and not ws.get("topic"):
        if st.sidebar.button("一键填入示例选题", key=f"{key}_fill_demo"):
            ws["topic"] = dict(DEMO_WORKSHOP_TOPIC)
            st.rerun()

    topic = ws.get("topic", {})
    t_title = st.text_input("选题标题", value=topic.get("title", ""), key=f"{key}_title")
    t_angle = st.text_area("选题角度", value=topic.get("angle", ""), height=70, key=f"{key}_angle")
    t_content = st.text_area("素材正文", value=topic.get("content", ""), height=140, key=f"{key}_content")

    if st.button(f"开始{platform}生产", key=f"btn_{key}_build", type="primary"):
        if not t_title.strip():
            st.warning("请填写选题标题。")
        else:
            with st.spinner(f"正在按{platform}平台规则生产..."):
                try:
                    report = produce_for_platform(
                        platform, track, t_title.strip(), t_angle.strip(), t_content.strip(),
                        persona_description,
                    )
                    ws["report"] = report
                    ws["topic"] = {"title": t_title.strip(), "angle": t_angle.strip(), "content": t_content.strip()}
                    db_utils.save_content_asset(
                        asset_type="report", channel=platform, title=t_title.strip(),
                        content=report["platform_markdown"],
                        search_keywords="、".join(k.get("keyword", "") for k in report["search_keywords"][:3]),
                    )
                    st.success(f"{platform}生产完成，报告已保存到内容资产。")
                except Exception as e:
                    st.error(f"{platform}生产失败：{e}")

    report = ws.get("report")
    if report:
        checks = report["checks"]
        st.markdown("### 生产摘要")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("搜索词", len(report["search_keywords"]))
        with c2:
            passed = sum(1 for t in report["titles"] if t.get("keyword_check", {}).get("passed"))
            st.metric("标题通过关键词检查", f"{passed}/{len(report['titles'])}")
        with c3:
            wc = report["copy"].get("word_count", {})
            st.metric("正文字数", wc.get("chars", "-"))
        with c4:
            ic = checks["interaction"]
            ok = all(v.get("passed") for v in ic.values())
            st.metric("互动策略检查", "✅" if ok else "⚠️")

        st.markdown("### 选题角度建议（平台视角）")
        for a in report["topic_angles"]:
            st.markdown(f"- **{a.get('angle')}**：{a.get('rationale', '')}")

        st.markdown("### 标题方案")
        for t in report["titles"]:
            flag = "✅" if t.get("keyword_check", {}).get("passed") else "⚠️ 关键词未前置"
            st.markdown(f"- {t.get('title')}（{t.get('formula_type', '')}）{flag}")

        st.markdown("### 封面提示词")
        cover = report["cover"]
        st.markdown(f"- **主体：** {cover.get('subject', '')}")
        st.markdown(f"- **风格：** {cover.get('style', '')}")
        st.markdown(f"- **构图：** {cover.get('composition', '')}")
        st.markdown(f"- **文字位：** {cover.get('text_slot', '')}")
        st.markdown(f"- **平台规格：** {cover.get('spec_note', '')}")

        st.markdown("### 平台正文")
        st.markdown(report["copy"].get("content", ""))
        st.caption(f"结构说明：{report['copy'].get('structure_note', '')}")

        st.markdown("### 互动策略（收藏/转发/评论）")
        inter = report["interaction"]
        st.markdown("**收藏/划线理由：**")
        for r in inter.get("collect_reasons", []):
            st.markdown(f"- {r}")
        st.markdown("**转发/分享引导：**")
        for r in inter.get("share_guides", []):
            st.markdown(f"- {r}")
        st.markdown("**评论区引导：**")
        for r in inter.get("comment_guides", []):
            st.markdown(f"- {r}")
        st.markdown(f"**策略说明：** {inter.get('strategy_note', '')}")

        st.markdown("### 下载与规则卡")
        st.download_button(
            f"下载{platform}生产报告.md",
            data=report["platform_markdown"],
            file_name=f"{platform}生产报告-{report['topic']['title'][:20]}.md",
            mime="text/markdown",
            key=f"btn_{key}_download",
        )
        with st.expander(f"查看{platform}平台规则卡"):
            st.text(report["rule_card"])
        with st.expander("预览完整报告"):
            st.text(report["platform_markdown"])
