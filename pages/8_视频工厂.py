"""
视频工厂（M2）— AI 超级自媒体工具

流程：视频选题 → 秒级分镜脚本(时间轴校验) → 视频标题/封面 → 播放优化(收藏指令检查) → 互动策略
分镜脚本是跨模型可复用资产，不绑定单一视频生成模型。
"""
import json
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.video_script_storyboarder import generate_video_script, DURATION_TEMPLATES
from agents.video_play_optimizer import optimize_video_play
from agents.video_interaction_strategist import generate_video_interaction
from agents.title_optimizer import generate_title_variants
from agents.cover_prompt_generator import generate_cover_prompt
from agents.search_keyword_analyzer import analyze_search_keywords
from database import db_utils
from utils.rule_checks import check_title_keywords, scan_red_lines
from utils.ui_components import inject_custom_css
from utils.demo_data import render_demo_toggle, DEMO_TOPIC

VIDEO_CHANNELS = ["抖音", "视频号", "小红书"]

st.set_page_config(page_title="视频工厂", layout="wide")
inject_custom_css()

if "video_factory" not in st.session_state:
    st.session_state.video_factory = {}

db_utils.init_db()
db_utils.ensure_default_persona()

_default_persona = db_utils.get_default_persona()
DEFAULT_PERSONA = _default_persona["persona_description"] if _default_persona else ""

st.markdown(
    '<div class="page-header"><h1>视频工厂</h1>'
    "<p>选题 → 秒级分镜 → 标题/封面 → 播放优化 → 互动策略，时间轴与收藏指令由代码校验</p></div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown('<div class="sidebar-header">视频工厂配置</div>', unsafe_allow_html=True)
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

vf = st.session_state.video_factory

if demo_on and not vf.get("topic"):
    if st.sidebar.button("一键填入示例选题", key="vf_fill_demo"):
        vf["topic"] = dict(DEMO_TOPIC)
        st.rerun()

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["① 视频选题", "② 分镜脚本", "③ 标题与封面", "④ 播放优化", "⑤ 互动策略"]
)

# ══════════════ Step 1: 视频选题 ══════════════
with tab1:
    st.subheader("视频选题")
    st.caption("选题可复用图文工厂的素材，或单独输入。时长模板：30s 口播 / 60s 干货 / 180s 中长视频（平台扶持，长尾 90 天）。")
    topic = vf.get("topic", {})
    v_title = st.text_input("选题标题", value=topic.get("title", ""), key="vf_topic_title")
    v_angle = st.text_area("选题角度", value=topic.get("angle", ""), height=70, key="vf_topic_angle")
    v_content = st.text_area("素材要点", value=topic.get("content", ""), height=120, key="vf_topic_content")

    c1, c2 = st.columns(2)
    with c1:
        duration_choice = st.selectbox("时长模板", ["60", "30", "180"], index=0, key="vf_duration",
                                       format_func=lambda x: f"{x} 秒")
    with c2:
        video_channel = st.selectbox("目标平台", VIDEO_CHANNELS, index=0, key="vf_channel")

    if st.button("保存视频选题", key="btn_vf_save_topic", type="primary"):
        if not v_title.strip():
            st.warning("请填写选题标题。")
        else:
            vf["topic"] = {"title": v_title.strip(), "angle": v_angle.strip(), "content": v_content.strip()}
            vf["duration"] = int(duration_choice)
            vf["channel"] = video_channel
            st.success(f"视频选题已保存（{vf['duration']}s / {video_channel}），请进入②生成分镜脚本。")

# ══════════════ Step 2: 分镜脚本 ══════════════
with tab2:
    st.subheader("秒级分镜脚本")
    st.caption("分镜含画面/口播/字幕/转场，时间轴连续性由代码校验，可直接用于口播录制或后续接入视频生成 API。")

    if not vf.get("topic"):
        st.info("请先在①保存视频选题。")
    else:
        if st.button("生成分镜脚本", key="btn_vf_script", type="primary"):
            with st.spinner("AI 正在编排分镜..."):
                try:
                    if not vf.get("search_keywords"):
                        vf["search_keywords"] = analyze_search_keywords(
                            track, vf["topic"]["title"], vf["topic"].get("angle", ""), persona_description
                        )
                    script = generate_video_script(
                        track, vf["topic"]["title"], vf["topic"].get("angle", ""),
                        vf["channel"], vf["duration"], vf["search_keywords"], persona_description,
                    )
                    vf["script"] = script
                    db_utils.save_content_asset(
                        asset_type="script", channel=vf["channel"], title=vf["topic"]["title"],
                        content=json.dumps(script, ensure_ascii=False), search_keywords="、".join(
                            k.get("keyword", "") for k in vf["search_keywords"][:3]),
                    )
                    st.success("分镜脚本已生成并入库。")
                except Exception as e:
                    st.error(f"分镜生成失败：{e}")

        script = vf.get("script")
        if script:
            tl = script.get("checks", {}).get("timeline", {})
            cta = script.get("checks", {}).get("closing_cta", {})
            if tl.get("passed"):
                st.success(f"时间轴校验通过：{tl['shot_count']} 个镜头，共 {tl['total_seconds']}s（目标 {tl['target_seconds']}s）。")
            else:
                st.error("时间轴校验未通过：")
                for issue in tl.get("issues", []):
                    st.markdown(f"- {issue}")
            if not cta.get("present"):
                st.warning("结尾缺少显性收藏指令（建议收藏/先收藏/收藏起来）。")
            from agents.compliance_checker import AI_LABEL_TEMPLATES
            st.info(f"AI 标注（发布时需附带）：{AI_LABEL_TEMPLATES.get(vf['channel'], '本视频由 AI 辅助创作')}")

            st.markdown(f"**标题钩子方向：** {script.get('video_title_hook', '')}")
            st.markdown(f"**结尾行动指令：** {script.get('closing_cta', '')}")
            st.markdown("**分镜表：**")
            rows = []
            for shot in script.get("storyboard", []):
                rows.append({
                    "时间": f"{shot.get('time_start')}s-{shot.get('time_end')}s",
                    "场景": shot.get("scene", ""),
                    "画面": shot.get("visual", ""),
                    "口播": shot.get("voiceover", ""),
                    "字幕": shot.get("subtitle", ""),
                    "转场": shot.get("transition", ""),
                })
            st.dataframe(rows, use_container_width=True, height=360)

# ══════════════ Step 3: 标题与封面 ══════════════
with tab3:
    st.subheader("视频标题与封面")
    st.caption("视频标题走平台差异化（抖音钩子型/视频号人设型），封面复用封面提示词 Agent（视频画面向）。")

    if not vf.get("script"):
        st.info("请先在②生成分镜脚本。")
    else:
        if st.button("生成视频标题（带关键词检查）", key="btn_vf_titles", type="primary"):
            with st.spinner("AI 正在生成视频标题..."):
                try:
                    variants = generate_title_variants(
                        track, vf["topic"]["title"], vf["topic"].get("angle", ""),
                        persona_description, variant_count=5,
                    )
                    kw_list = [k.get("keyword", "") for k in vf.get("search_keywords", [])]
                    for v in variants:
                        v["keyword_check"] = check_title_keywords(v.get("title", ""), kw_list)
                    vf["titles"] = variants
                except Exception as e:
                    st.error(f"标题生成失败：{e}")

        variants = vf.get("titles")
        if variants:
            for i, v in enumerate(variants, 1):
                kc = v.get("keyword_check", {})
                flag = "✅" if kc.get("passed") else "⚠️"
                with st.container(border=True):
                    st.markdown(f"**{i}. {v.get('title', '')}**  {flag}")
                    st.caption(f"公式：{v.get('formula_type', '-')} ｜ 思路：{v.get('rationale', '-')}")
                    if kc and kc.get("missing"):
                        st.warning(f"前20字未命中关键词：{kc['missing']}")

        if st.button("生成视频封面提示词", key="btn_vf_cover", type="primary"):
            with st.spinner("AI 正在设计视频封面..."):
                try:
                    kws_text = "、".join(k.get("keyword", "") for k in vf.get("search_keywords", [])[:3])
                    cover = generate_cover_prompt(
                        track, vf["topic"]["title"], vf["channel"], "视频笔记", kws_text
                    )
                    vf["cover"] = cover
                    st.success("视频封面提示词已生成。")
                except Exception as e:
                    st.error(f"封面生成失败：{e}")

        cover = vf.get("cover")
        if cover:
            comp = cover.get("completeness", {})
            if comp.get("passed"):
                st.success("封面完整性校验通过。")
            else:
                st.warning(comp.get("suggestion", ""))
            st.markdown(f"**主体：** {cover.get('subject', '')}")
            st.markdown(f"**文字位：** {cover.get('text_slot', '')}")
            st.markdown(f"**风格：** {cover.get('style', '')}")
            st.markdown(f"**构图：** {cover.get('composition', '')}")

# ══════════════ Step 4: 播放优化 ══════════════
with tab4:
    st.subheader("播放优化")
    st.caption("2026 抖音权重：5 秒完播 > 完播率 > 收藏率。前 5 秒钩子与显性收藏指令由代码检查兜底。")

    if not vf.get("script"):
        st.info("请先在②生成分镜脚本。")
    else:
        if st.button("生成播放优化方案", key="btn_vf_play", type="primary"):
            with st.spinner("AI 正在诊断播放表现..."):
                try:
                    script_text = json.dumps(vf["script"].get("storyboard", []), ensure_ascii=False, indent=1)
                    play = optimize_video_play(
                        track, vf["topic"]["title"], vf["channel"], vf["duration"], script_text
                    )
                    vf["play"] = play
                    st.success("播放优化方案已生成。")
                except Exception as e:
                    st.error(f"播放优化失败：{e}")

        play = vf.get("play")
        if play:
            checks = play.get("checks", {})
            cc = checks.get("collect_cta", {})
            hk = checks.get("hook", {})
            if cc.get("passed"):
                st.success(f"收藏指令检查通过（「{cc['matched']}」）。")
            else:
                st.warning(cc.get("suggestion", ""))
            if hk.get("passed"):
                st.success(f"前 5 秒钩子检查通过（{hk['chars']} 字）。")
            else:
                st.warning(hk.get("suggestion", ""))

            st.markdown(f"**前 5 秒钩子（可直接替换开头）：** {play.get('five_sec_hook', '')}")
            st.markdown(f"**钩子评估：** {play.get('hook_assessment', '')}")
            st.markdown(f"**显性收藏指令：** {play.get('collect_cta', '')}")
            st.markdown("**完播优化建议：**")
            for t in play.get("completion_tips", []):
                st.markdown(f"- {t}")
            st.markdown("**字幕优化建议：**")
            for t in play.get("subtitle_tips", []):
                st.markdown(f"- {t}")
            st.markdown("**风险提示：**")
            for r in play.get("risks", []):
                st.markdown(f"- {r}")

# ══════════════ Step 5: 互动策略 ══════════════
with tab5:
    st.subheader("互动策略")
    st.caption("视频号社交推荐权重翻倍，评论数是公域流量入口核心指标。置顶评论相当于第二次标题。")

    if not vf.get("play"):
        st.info("请先在④生成播放优化方案。")
    else:
        if st.button("生成互动策略", key="btn_vf_interaction", type="primary"):
            with st.spinner("AI 正在设计互动策略..."):
                try:
                    summary = json.dumps(vf["script"].get("storyboard", [])[:3], ensure_ascii=False)
                    interaction = generate_video_interaction(
                        track, vf["topic"]["title"], vf["channel"], summary
                    )
                    vf["interaction"] = interaction
                    st.success("互动策略已生成。")
                except Exception as e:
                    st.error(f"互动策略失败：{e}")

        interaction = vf.get("interaction")
        if interaction:
            rl = interaction.get("checks", {}).get("red_lines", {})
            if rl.get("hits"):
                st.error("红线词复核未通过：" + "；".join(f"{h['category']}：{h['word']}" for h in rl["hits"]))
            else:
                st.success("红线词复核通过。")

            st.markdown(f"**置顶评论：** {interaction.get('comment_pin', '')}")
            st.markdown("**评论区引导：**")
            for q in interaction.get("engagement_questions", []):
                st.markdown(f"- {q}")
            st.markdown("**分享理由：**")
            for r in interaction.get("share_reasons", []):
                st.markdown(f"- {r}")
            st.markdown(f"**回复策略：** {interaction.get('reply_strategy', '')}")
            st.markdown("**风险规避：**")
            for r in interaction.get("risk_notes", []):
                st.markdown(f"- {r}")
