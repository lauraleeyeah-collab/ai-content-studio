"""
渠道中心（M3）— AI 超级自媒体工具（核心差异化模块）

平台规则库（6平台可编辑）→ 一键多平台改写 → 合规检查 → 发布清单导出
同一份素材按平台规则适配，不是复制粘贴。
"""
import json
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.channel_rewriter import rewrite_multi_channel, ALL_CHANNELS
from agents.compliance_checker import check_compliance
from database import db_utils
from utils.ui_components import inject_custom_css, render_api_key_input
from utils.demo_data import render_demo_toggle, DEMO_TOPIC

st.set_page_config(page_title="渠道中心", layout="wide")
inject_custom_css()

db_utils.init_db()
db_utils.init_channels()

if "channel_center" not in st.session_state:
    st.session_state.channel_center = {}

cc = st.session_state.channel_center
db_utils.ensure_default_persona()

_default_persona = db_utils.get_default_persona()
DEFAULT_PERSONA = _default_persona["persona_description"] if _default_persona else ""

st.markdown(
    '<div class="page-header"><h1>渠道中心</h1>'
    "<p>6 平台规则库 → 一键多平台改写 → 合规检查 → 发布清单，平台规则适配是本产品核心差异化</p></div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown('<div class="sidebar-header">渠道中心配置</div>', unsafe_allow_html=True)
    demo_on = render_demo_toggle()
    render_api_key_input()
    track = st.text_input("赛道关键词", value="AI工具/自我提升")
    persona_description = st.text_area("账号人设描述", value=DEFAULT_PERSONA, height=100)

if demo_on and not cc.get("source"):
    if st.sidebar.button("一键填入示例素材", key="cc_fill_demo"):
        cc["source"] = {
            "title": DEMO_TOPIC["title"],
            "content": "用AI写周报半年，从被领导说'像流水账'到被评为'重点周报'。核心3个提示词技巧：给AI角色设定、喂结构化素材、追加追问让进度量化。数据和结论一定要自己核对。",
        }
        st.rerun()

tab1, tab2, tab3, tab4 = st.tabs(["① 平台规则库", "② 一键多平台改写", "③ 发布清单", "④ 合规检查"])

# ══════════════ Tab 1: 平台规则库 ══════════════
with tab1:
    st.subheader("6 平台规则库")
    st.caption("规则卡基于 2026 平台调研沉淀（见 docs/调研报告），可编辑保存，规则变化时随时迭代。")
    channels = db_utils.get_channels()
    for ch in channels:
        with st.expander(f"{ch['name']}" + ("（强制 AI 标注）" if ch.get("ai_label_required") else "（暂未强制标注）")):
            algo = st.text_area("算法权重", value=ch.get("algorithm_weights", ""), key=f"algo_{ch['name']}", height=60)
            prefs = st.text_area("内容偏好", value=ch.get("content_prefs", ""), key=f"prefs_{ch['name']}", height=80)
            red = st.text_area("红线", value=ch.get("red_lines", ""), key=f"red_{ch['name']}", height=60)
            bp = st.text_area("最佳实践", value=ch.get("best_practices", ""), key=f"bp_{ch['name']}", height=80)
            spec = st.text_area("平台规格（封面/正文/标题/互动机制，供平台工作台使用）",
                                value=ch.get("platform_spec", ""), key=f"spec_{ch['name']}", height=100)
            ck = st.text_input("收藏引导关键词（逗号分隔）", value=ch.get("collect_keywords", ""), key=f"ck_{ch['name']}")
            sk = st.text_input("分享引导关键词（逗号分隔）", value=ch.get("share_keywords", ""), key=f"sk_{ch['name']}")
            cw1, cw2 = st.columns(2)
            with cw1:
                cmin = st.number_input("正文字数下限", min_value=0, value=int(ch.get("copy_min_words") or 0),
                                       key=f"cmin_{ch['name']}")
            with cw2:
                cmax = st.number_input("正文字数上限", min_value=0, value=int(ch.get("copy_max_words") or 0),
                                       key=f"cmax_{ch['name']}")
            label_req = st.checkbox("强制 AI 标注", value=bool(ch.get("ai_label_required")), key=f"label_{ch['name']}")
            if st.button("保存规则", key=f"save_{ch['name']}"):
                db_utils.update_channel_rule(
                    ch["name"],
                    algorithm_weights=algo, content_prefs=prefs,
                    red_lines=red, best_practices=bp,
                    platform_spec=spec, collect_keywords=ck, share_keywords=sk,
                    copy_min_words=int(cmin), copy_max_words=int(cmax),
                    ai_label_required=1 if label_req else 0,
                )
                st.success(f"{ch['name']} 规则已更新。")

# ══════════════ Tab 2: 一键多平台改写 ══════════════
with tab2:
    st.subheader("一键多平台改写")
    st.caption("同一份素材按平台规则改写，输出每个版本 + 改写理由。改写流程先验证小红书/抖音/视频号 3 个高频平台（PRD 已确认），其余平台一并支持。")

    source = cc.get("source", {})
    src_title = st.text_input("素材标题", value=source.get("title", ""), key="cc_title")
    src_content = st.text_area("素材正文", value=source.get("content", ""), height=160, key="cc_content")

    selected = st.multiselect("目标平台", ALL_CHANNELS, default=["小红书", "抖音", "视频号"], key="cc_channels")
    kws_text = st.text_input("核心搜索词（逗号分隔）", value="AI写周报, AI提效工具", key="cc_kws")

    if st.button("一键改写", key="btn_cc_rewrite", type="primary"):
        if not src_title.strip():
            st.warning("请填写素材标题。")
        elif not selected:
            st.warning("请至少选择一个目标平台。")
        else:
            with st.spinner(f"AI 正在按 {len(selected)} 个平台规则改写..."):
                try:
                    kws = [{"keyword": k.strip()} for k in kws_text.split(",") if k.strip()]
                    results = rewrite_multi_channel(
                        src_title.strip(), src_content.strip(), selected, kws, persona_description
                    )
                    cc["rewrites"] = results
                    cc["source"] = {"title": src_title.strip(), "content": src_content.strip()}
                    st.success(f"已生成 {len(results)} 个平台版本。")
                except Exception as e:
                    st.error(f"渠道改写失败：{e}")

    rewrites = cc.get("rewrites")
    if rewrites:
        st.markdown("### 各平台版本")
        for rw in rewrites:
            ch = rw.get("channel", "")
            rl = rw.get("code_checks", {}).get("red_lines", {})
            with st.expander(f"{ch} 版本" + (" ✅ 红线通过" if rl.get("passed") else " ⚠️ 命中红线")):
                st.text_area("内容（可编辑）", value=rw.get("content", ""), height=180, key=f"rw_{ch}")
                st.markdown("**一键复制（点代码块右上角图标）：**")
                st.code(rw.get("content", ""), language="markdown")
                st.caption("改写理由：" + "；".join(rw.get("rewrite_reasons", [])))
                st.caption("发布提示：" + "；".join(rw.get("publish_tips", [])))
                if rw.get("ai_label", {}).get("required"):
                    st.info(f"AI 标注（必确认）：{rw['ai_label']['template']}")
                if rl.get("hits"):
                    st.error("命中红线：" + "；".join(f"{h['category']}：{h['word']}" for h in rl["hits"]))

        if st.button("保存改写版本到记录", key="btn_cc_save"):
            n = 0
            for rw in rewrites:
                db_utils.save_channel_rewrite(
                    source_asset_id=0, target_channel=rw.get("channel", ""),
                    rewritten_content=rw.get("content", ""),
                    rewrite_reasons="；".join(rw.get("rewrite_reasons", [])),
                    compliance_result=json.dumps(rw.get("code_checks", {}), ensure_ascii=False),
                )
                n += 1
            st.success(f"已保存 {n} 条改写记录。")

# ══════════════ Tab 3: 发布清单 ══════════════
with tab3:
    st.subheader("发布清单")
    st.caption("把平台版本组装为发布清单，AI 标注必须逐平台确认后才允许导出（2026 平台强制）。")

    rewrites = cc.get("rewrites")
    if not rewrites:
        st.info("请先在②一键改写生成平台版本。")
    else:
        st.markdown("**逐平台确认（AI 标注 / 合规）：**")
        confirmations = {}
        all_confirmed = True
        for rw in rewrites:
            ch = rw.get("channel", "")
            rl = rw.get("code_checks", {}).get("red_lines", {})
            needs_label = rw.get("ai_label", {}).get("required", False)
            c1 = st.checkbox(f"{ch}：红线检查通过" if rl.get("passed") else f"{ch}：存在红线需处理",
                             value=bool(rl.get("passed")), key=f"conf_red_{ch}")
            c2 = True
            if needs_label:
                c2 = st.checkbox(f"{ch}：已确认 AI 标注文案「{rw['ai_label']['template']}」", key=f"conf_label_{ch}")
            confirmations[ch] = c1 and c2
            if not (c1 and c2):
                all_confirmed = False

        publish_time = st.text_input("计划发布时间", value="2026-08-13 20:00", key="cc_publish_time")

        if st.button("生成发布清单（Markdown）", key="btn_cc_list", type="primary"):
            if not all_confirmed:
                st.warning("存在未确认项：红线未处理或 AI 标注未确认，不允许导出。")
            else:
                lines = [
                    "# 发布清单",
                    "",
                    f"**素材：** {cc.get('source', {}).get('title', '')}",
                    f"**计划发布：** {publish_time}",
                    "",
                ]
                for rw in rewrites:
                    ch = rw.get("channel", "")
                    lines += [
                        f"## {ch}",
                        f"**标题：** {cc.get('source', {}).get('title', '')}",
                        "",
                        rw.get("content", ""),
                        "",
                        f"**AI 标注：** {rw.get('ai_label', {}).get('template', '')}",
                        f"**发布提示：** {'；'.join(rw.get('publish_tips', []))}",
                        "",
                    ]
                markdown = "\n".join(lines)
                cc["publish_list"] = markdown

                # 落库发布记录 + 同步加入内容日历（P1）
                for rw in rewrites:
                    date_part = (publish_time or "2026-08-13").split(" ")[0]
                    time_part = (publish_time or "20:00").split(" ")[1] if " " in (publish_time or "") else "20:00"
                    db_utils.save_schedule(
                        asset_id=0, channel=rw.get("channel", ""),
                        content_title=cc.get("source", {}).get("title", ""),
                        planned_date=date_part, planned_time=time_part,
                        persona_name=(db_utils.get_default_persona() or {}).get("name", ""),
                    )
                    db_utils.save_publish_record(
                        asset_id=0, channel=rw.get("channel", ""),
                        final_title=cc.get("source", {}).get("title", ""),
                        final_content=rw.get("content", ""),
                        checklist_json=json.dumps({"ai_label": rw.get("ai_label", {}),
                                                   "red_lines": rw.get("code_checks", {}).get("red_lines", {})},
                                                  ensure_ascii=False),
                        publish_time=publish_time, status="ready",
                    )
                st.success("发布清单已生成并保存发布记录。")

        if cc.get("publish_list"):
            st.download_button(
                "下载发布清单.md",
                data=cc["publish_list"],
                file_name=f"发布清单-{cc.get('source', {}).get('title', '')[:20]}.md",
                mime="text/markdown",
                key="btn_download_list",
            )
            with st.expander("预览发布清单"):
                st.text(cc["publish_list"])

# ══════════════ Tab 4: 合规检查 ══════════════
with tab4:
    st.subheader("合规检查")
    st.caption("双层检查：代码词表硬校验（确定性）+ LLM 语义判断（隐含极限词/软广/诱导）。")
    check_text = st.text_area("待检查内容", height=200, key="cc_check_text",
                              placeholder="粘贴要发布的正文/脚本/话术...")
    check_channel = st.selectbox("目标平台", ALL_CHANNELS, index=0, key="cc_check_channel")
    if st.button("执行合规检查", key="btn_cc_compliance", type="primary"):
        if not check_text.strip():
            st.warning("请粘贴待检查内容。")
        else:
            with st.spinner("正在执行双重合规检查..."):
                try:
                    rule = db_utils.get_channel_rule(check_channel) or {}
                    result = check_compliance(
                        check_text.strip(), check_channel,
                        red_lines=rule.get("red_lines", ""),
                        ai_label_required=bool(rule.get("ai_label_required", True)),
                    )
                    cc["compliance"] = {"channel": check_channel, **result}
                except Exception as e:
                    st.error(f"合规检查失败：{e}")

    result = cc.get("compliance")
    if result:
        passed = result.get("passed")
        st.success("✅ 合规检查通过，可发布。") if passed else st.error("⚠️ 存在风险，建议修改后再发布。")
        rl = result.get("code_checks", {}).get("red_lines", {})
        if rl.get("hits"):
            st.markdown("**代码词表命中：**")
            for h in rl["hits"]:
                st.markdown(f"- {h['category']}：`{h['word']}`")
        llm = result.get("llm", {})
        if llm.get("llm_findings"):
            st.markdown("**LLM 语义判断：**")
            for f in llm["llm_findings"]:
                st.markdown(f"- [{f.get('level', '')}] {f.get('risk', '')} → {f.get('suggestion', '')}")
        st.markdown(f"**AI 标注建议：** {llm.get('ai_label_suggestion', '-')}")
        ai = result.get("ai_label", {})
        if ai.get("required"):
            st.info(f"该平台要求 AI 标注，建议文案：{ai.get('template', '')}")
        st.caption(f"结论：{llm.get('summary', '')}")
