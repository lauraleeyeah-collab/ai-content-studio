"""
图文工厂（M1）— AI 超级自媒体工具

流程：选题输入 → 搜索词分析 → 标题生成(关键词前20字检查) → 封面提示词 → 正文平台改写 → 互动话术
所有 AI 判断由 Agent 完成，所有校验（关键词位置/字数/红线/封面完整性/收藏指令）由确定性代码完成。
"""
import json
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.search_keyword_analyzer import analyze_search_keywords
from agents.title_optimizer import generate_title_variants
from agents.cover_prompt_generator import generate_cover_prompt
from agents.platform_copywriter import rewrite_for_channel, SUPPORTED_CHANNELS
from agents.interaction_copywriter import generate_interaction_copy
from database import db_utils
from utils.rule_checks import check_title_keywords, scan_red_lines
from utils.ui_components import inject_custom_css, render_api_key_input
from utils.demo_data import render_demo_toggle, DEMO_TOPIC

st.set_page_config(page_title="图文工厂", layout="wide")
inject_custom_css()

if "factory" not in st.session_state:
    st.session_state.factory = {}

db_utils.init_db()
db_utils.ensure_default_persona()

_default_persona = db_utils.get_default_persona()
DEFAULT_PERSONA = _default_persona["persona_description"] if _default_persona else ""

st.markdown(
    '<div class="page-header"><h1>图文工厂</h1>'
    "<p>选题 → 搜索词 → 标题 → 封面 → 正文 → 互动话术，每一步都有确定性校验兜底</p></div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown('<div class="sidebar-header">图文工厂配置</div>', unsafe_allow_html=True)
    demo_on = render_demo_toggle()
    render_api_key_input()
    track = st.text_input("赛道关键词", value="AI工具/自我提升")
    persona_description = st.text_area("账号人设描述", value=DEFAULT_PERSONA, height=120)

factory = st.session_state.factory

# ── 演示模式一键填充 ──
if demo_on and not factory.get("topic"):
    if st.sidebar.button("一键填入示例选题", key="factory_fill_demo"):
        factory["topic"] = dict(DEMO_TOPIC)
        st.rerun()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["① 选题输入", "② 搜索词分析", "③ 标题生成", "④ 封面提示词", "⑤ 正文改写", "⑥ 互动话术"]
)

# ══════════════ Step 1: 选题输入 ══════════════
with tab1:
    st.subheader("选题输入")
    st.caption("支持手动输入，或从历史选题复用（演示模式可一键填入示例）。")
    topic = factory.get("topic", {})
    t_title = st.text_input("选题标题", value=topic.get("title", ""), key="f_topic_title")
    t_angle = st.text_area("选题角度", value=topic.get("angle", ""), height=80, key="f_topic_angle",
                           placeholder="差异化视角，如：真实使用记录 / 避坑 / 清单对比...")
    t_content = st.text_area("素材正文/大纲", value=topic.get("content", ""), height=180, key="f_topic_content",
                             placeholder="粘贴素材正文、笔记原文或大纲要点，供搜索词分析与平台改写使用")

    if st.button("保存选题并进入搜索词分析", key="btn_save_topic", type="primary"):
        if not t_title.strip():
            st.warning("请填写选题标题。")
        else:
            factory["topic"] = {"title": t_title.strip(), "angle": t_angle.strip(), "content": t_content.strip()}
            # 保存内容资产
            asset_id = db_utils.save_content_asset(
                asset_type="topic", channel=track, title=t_title.strip(),
                content=t_content.strip(), persona_name=persona_description[:50],
            )
            factory["topic_asset_id"] = asset_id
            st.success(f"选题已保存（资产ID {asset_id}），请进入②搜索词分析。")

# ══════════════ Step 2: 搜索词分析 ══════════════
with tab2:
    st.subheader("搜索词分析")
    st.caption("2026 平台趋势：搜索流量为核心分发渠道，选题必须先回答「用户会搜什么」。")

    if not factory.get("topic"):
        st.info("请先在①填写并保存选题。")
    else:
        if st.button("生成搜索词清单", key="btn_gen_keywords", type="primary"):
            with st.spinner("AI 正在拆解用户搜索意图..."):
                try:
                    kws = analyze_search_keywords(
                        track, factory["topic"]["title"], factory["topic"].get("angle", ""), persona_description
                    )
                    factory["search_keywords"] = kws
                    saved = db_utils.save_search_keywords(track, kws, factory["topic"]["title"])
                    st.success(f"已生成 {len(kws)} 个搜索词并入库（{saved} 条）。")
                except Exception as e:
                    st.error(f"搜索词分析失败：{e}")

        kws = factory.get("search_keywords")
        if kws:
            st.write("搜索词清单（按优先级排序，可直接编辑后用于下一步）：")
            edited = st.text_area(
                "JSON 编辑", value=json.dumps(kws, ensure_ascii=False, indent=1), height=260, key="f_keywords_json"
            )
            if st.button("应用编辑", key="btn_apply_keywords"):
                try:
                    parsed = json.loads(edited)
                    factory["search_keywords"] = parsed
                    st.success("搜索词已更新。")
                except json.JSONDecodeError:
                    st.error("JSON 格式错误，请检查后重试。")

            top_kws = [k.get("keyword", "") for k in kws[:3]]
            st.markdown("**优先级 Top3（用于标题关键词检查）：** " + " / ".join(f"`{k}`" for k in top_kws))

# ══════════════ Step 3: 标题生成 ══════════════
with tab3:
    st.subheader("标题生成 + 关键词位置检查")
    st.caption("小红书搜索流量超 55%，标题前 20 字必须放长尾关键词——由代码逐条检查，不靠模型自觉。")

    kws = factory.get("search_keywords")
    if not kws:
        st.info("请先在②生成搜索词。")
    else:
        if st.button("生成标题变体（带关键词检查）", key="btn_gen_titles", type="primary"):
            with st.spinner("AI 正在生成标题变体..."):
                try:
                    variants = generate_title_variants(
                        track, factory["topic"]["title"], factory["topic"].get("angle", ""),
                        persona_description, variant_count=5,
                    )
                    # 代码级关键词检查
                    keyword_list = [k.get("keyword", "") for k in kws]
                    for v in variants:
                        v["keyword_check"] = check_title_keywords(v.get("title", ""), keyword_list)
                    factory["title_variants"] = variants
                    st.success("标题已生成并完成关键词检查。")
                except Exception as e:
                    st.error(f"标题生成失败：{e}")

        variants = factory.get("title_variants")
        if variants:
            for i, v in enumerate(variants, 1):
                kc = v.get("keyword_check", {})
                flag = "✅" if kc.get("passed") else "⚠️"
                with st.container(border=True):
                    st.markdown(f"**{i}. {v.get('title', '')}**  {flag}")
                    st.caption(f"公式：{v.get('formula_type', '-')} ｜ 思路：{v.get('rationale', '-')}")
                    if kc:
                        st.markdown(
                            f"关键词检查：前缀命中 `{kc['matched_in_prefix'] or '无'}` ｜ "
                            f"未出现 `{kc['missing'] or '无'}`"
                        )
                        if kc.get("suggestion"):
                            st.warning(kc["suggestion"])

# ══════════════ Step 4: 封面提示词 ══════════════
with tab4:
    st.subheader("封面提示词")
    st.caption("产出可直接用于 AI 生图工具（即梦/可灵/豆包等）的封面提示词，含文字位设计。")

    if not factory.get("search_keywords"):
        st.info("请先在②生成搜索词。")
    else:
        channel_cover = st.selectbox("封面目标平台", ["小红书", "公众号", "知乎", "抖音"], index=0, key="f_cover_channel")
        if st.button("生成封面提示词", key="btn_gen_cover", type="primary"):
            with st.spinner("AI 正在设计封面..."):
                try:
                    kws_text = "、".join(k.get("keyword", "") for k in factory["search_keywords"][:3])
                    cover = generate_cover_prompt(
                        track, factory["topic"]["title"], channel_cover, "图文笔记", kws_text
                    )
                    factory["cover_prompt"] = cover
                    st.success("封面提示词已生成。")
                except Exception as e:
                    st.error(f"封面提示词生成失败：{e}")

        cover = factory.get("cover_prompt")
        if cover:
            comp = cover.get("completeness", {})
            if comp.get("passed"):
                st.success("完整性校验通过（主体/风格/构图/文字位齐全）。")
            else:
                st.warning(comp.get("suggestion", "提示词字段不完整。"))
            st.markdown(f"**主体：** {cover.get('subject', '')}")
            st.markdown(f"**风格：** {cover.get('style', '')}")
            st.markdown(f"**构图：** {cover.get('composition', '')}")
            st.markdown(f"**文字位：** {cover.get('text_slot', '')}")
            st.markdown(f"**配色：** {cover.get('color_scheme', '')}")
            st.markdown(f"**避免元素：** {', '.join(cover.get('negative_hint', []))}")
            if st.button("保存封面提示词到内容资产", key="btn_save_cover"):
                aid = db_utils.save_content_asset(
                    asset_type="cover", channel=channel_cover, title=factory["topic"]["title"],
                    content=json.dumps(cover, ensure_ascii=False), search_keywords="、".join(
                        k.get("keyword", "") for k in factory["search_keywords"][:3]),
                )
                st.success(f"封面提示词已入库（资产ID {aid}）。")

# ══════════════ Step 5: 正文改写 ══════════════
with tab5:
    st.subheader("正文平台改写")
    st.caption("同一素材按平台规则改写：小红书清单体 / 公众号长文 / 知乎结论先行 / 问一问高密度。字数与红线由代码校验。")

    if not factory.get("search_keywords"):
        st.info("请先在②生成搜索词。")
    else:
        target_channel = st.selectbox("目标平台", SUPPORTED_CHANNELS, index=0, key="f_copy_channel")
        if st.button("改写正文", key="btn_gen_copy", type="primary"):
            with st.spinner(f"AI 正在按{target_channel}规则改写..."):
                try:
                    rewritten = rewrite_for_channel(
                        track, factory["topic"]["title"], target_channel,
                        factory["topic"].get("content", ""), factory["search_keywords"], persona_description,
                    )
                    factory["rewritten"] = {"channel": target_channel, **rewritten}
                    st.success(f"{target_channel}版正文已生成。")
                except Exception as e:
                    st.error(f"正文改写失败：{e}")

        rewritten = factory.get("rewritten")
        if rewritten:
            st.markdown(f"**{rewritten['channel']}版正文**")
            st.text_area("正文（可编辑）", value=rewritten.get("content", ""), height=280,
                         key=f"f_copy_edit_{rewritten['channel']}")
            st.caption(f"结构：{rewritten.get('structure_note', '-')}")
            from agents.compliance_checker import AI_LABEL_TEMPLATES
            st.info(f"AI 标注（发布时需附带）：{AI_LABEL_TEMPLATES.get(rewritten['channel'], '本文由 AI 辅助创作')}")
            reasons = rewritten.get("rewrite_reasons") or []
            st.markdown("**改写理由：** " + "；".join(reasons))

            checks = rewritten.get("checks", {})
            wc = checks.get("word_count", {})
            rl = checks.get("red_lines", {})
            kc = checks.get("keyword_coverage", {})
            col1, col2, col3 = st.columns(3)
            with col1:
                status_icon = "✅" if wc.get("status") == "ok" else "⚠️"
                st.metric("字数校验", f"{wc.get('chars', 0)}字", f"{status_icon} {wc.get('status', '-')}")
            with col2:
                st.metric("红线词扫描", "通过" if rl.get("passed") else f"命中{len(rl.get('hits', []))}条")
            with col3:
                k_present = len(kc.get("present", []))
                st.metric("Top3关键词覆盖", f"{k_present}/3")
            if wc.get("suggestion"):
                st.info(wc["suggestion"])
            if rl.get("hits"):
                st.error("；".join(f"{h['category']}：{h['word']}" for h in rl["hits"]))
            if kc.get("missing"):
                st.warning(f"正文未覆盖搜索词：{kc['missing']}")
            if st.button("保存正文到内容资产", key="btn_save_copy"):
                aid = db_utils.save_content_asset(
                    asset_type="copy", channel=rewritten["channel"], title=factory["topic"]["title"],
                    content=rewritten.get("content", ""), search_keywords="、".join(
                        k.get("keyword", "") for k in factory["search_keywords"][:3]),
                    platform_review="；".join(reasons),
                )
                st.success(f"{rewritten['channel']}版正文已入库（资产ID {aid}）。")

# ══════════════ Step 6: 互动话术 ══════════════
with tab6:
    st.subheader("互动话术")
    st.caption("2026 权重趋势：收藏率第一（抖音）、评论数驱动社交推荐（视频号）。话术必须显性给收藏理由。")

    if not factory.get("rewritten"):
        st.info("请先在⑤生成平台版正文。")
    else:
        if st.button("生成互动话术", key="btn_gen_interaction", type="primary"):
            with st.spinner("AI 正在设计互动策略..."):
                try:
                    interaction = generate_interaction_copy(
                        track, factory["topic"]["title"], factory["rewritten"]["channel"],
                        factory["rewritten"].get("content", ""),
                    )
                    factory["interaction"] = interaction
                    st.success("互动话术已生成。")
                except Exception as e:
                    st.error(f"互动话术生成失败：{e}")

        interaction = factory.get("interaction")
        if interaction:
            checks = interaction.get("checks", {})
            cta_check = checks.get("collect_cta", {})
            if cta_check.get("passed"):
                st.success(f"收藏指令检查通过（命中「{cta_check['matched']}」）。")
            else:
                st.warning(cta_check.get("suggestion", "未检测到显性收藏指令。"))

            st.markdown("**收藏理由（可放正文结尾/评论区置顶）：**")
            for r in interaction.get("collect_reasons", []):
                st.markdown(f"- {r}")
            st.markdown("**评论区引导：**")
            for g in interaction.get("comment_guides", []):
                st.markdown(f"- {g}")
            st.markdown("**行动指令：**")
            for c in interaction.get("cta_suggestions", []):
                st.markdown(f"- {c}")
            st.caption(f"策略：{interaction.get('strategy_note', '-')}")

            # 对整页输出做一次红线复核
            all_text = " ".join(
                (interaction.get("collect_reasons") or []) + (interaction.get("cta_suggestions") or [])
            )
            rl = scan_red_lines(all_text)
            if rl.get("hits"):
                st.error("互动话术命中红线词：" + "；".join(f"{h['category']}：{h['word']}" for h in rl["hits"]))
