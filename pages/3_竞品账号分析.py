"""
竞品账号分析 — 深度分析竞品内容策略、发布规律、互动数据,提炼可借鉴套路。

流程:
1. 填写竞品账号基本信息并保存
2. 粘贴笔记原始文本,通过Agent 0提取结构化数据(或从流水线导入)
3. 勾选需要分析的笔记,一键生成分析报告
4. 查看统计图表 + LLM定性分析,保存分析结果
"""
import json
import os
import sys

import streamlit as st
import plotly.graph_objects as go

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.trend_collector import collect_trends
from agents.account_analyzer import analyze_account
from database import db_utils
from utils.ui_components import inject_custom_css
from utils.demo_data import render_demo_toggle

st.set_page_config(page_title="竞品账号分析", layout="wide")
inject_custom_css()

# ── 初始化 ──
db_utils.init_db()

_SESSION_KEYS = [
    "aa_account_info",
    "aa_account_id",
    "aa_extracted_notes",
    "aa_selected_indices",
    "aa_analysis_result",
]
for key in _SESSION_KEYS:
    if key not in st.session_state:
        st.session_state[key] = None

if "pipeline" not in st.session_state:
    st.session_state.pipeline = {}

# ── 页面标题 ──
st.markdown(
    '<div class="page-header"><h1>竞品账号分析</h1>'
    "<p>深度分析竞品账号的内容策略、发布规律、互动数据,发现可借鉴的套路与内容空白</p></div>",
    unsafe_allow_html=True,
)

# ── 侧栏 ──
with st.sidebar:
    st.markdown('<div class="sidebar-header">基础配置</div>', unsafe_allow_html=True)
    render_demo_toggle()
    api_key_input = st.text_input(
        "DashScope API Key",
        type="password",
        value=os.environ.get("DASHSCOPE_API_KEY", ""),
        help="在阿里云百炼/DashScope控制台获取。",
    )
    if api_key_input:
        os.environ["DASHSCOPE_API_KEY"] = api_key_input

    track = st.text_input("赛道关键词", value="AI工具/自我提升")

    st.divider()
    st.markdown('<div class="sidebar-header">已保存的竞品账号</div>', unsafe_allow_html=True)

    saved_accounts = db_utils.get_competitor_accounts()
    if saved_accounts:
        for acc in saved_accounts:
            label = f"{acc['account_name']} ({acc.get('fans_count', '?')} 粉)"
            if st.button(label, key=f"load_acc_{acc['id']}", width="stretch"):
                st.session_state.aa_account_info = {
                    "account_name": acc["account_name"],
                    "fans_count": acc.get("fans_count", 0),
                    "positioning": acc.get("positioning", ""),
                }
                st.session_state.aa_account_id = acc["id"]
                # 加载最近一次分析
                latest = db_utils.get_latest_account_analysis(acc["id"])
                if latest:
                    try:
                        st.session_state.aa_analysis_result = {
                            "computed_stats": json.loads(latest["computed_stats_json"]),
                            "llm_analysis": json.loads(latest["llm_analysis_json"]),
                        }
                    except (json.JSONDecodeError, TypeError):
                        st.session_state.aa_analysis_result = None
                # 加载笔记
                db_notes = db_utils.get_account_notes(acc["id"])
                if db_notes:
                    st.session_state.aa_extracted_notes = db_notes
                    st.session_state.aa_selected_indices = list(range(len(db_notes)))
                st.rerun()
    else:
        st.info("暂无已保存的竞品账号。")


# ══════════════════════════════════════════
# 第一部分: 账号基本信息
# ══════════════════════════════════════════

st.subheader("1. 账号基本信息")

with st.form("account_info_form"):
    existing = st.session_state.aa_account_info or {}
    col1, col2 = st.columns([2, 1])
    with col1:
        account_name = st.text_input(
            "账号名称",
            value=existing.get("account_name", ""),
            placeholder="输入竞品账号名称",
        )
    with col2:
        fans_count = st.number_input(
            "粉丝数",
            min_value=0,
            value=existing.get("fans_count", 0),
            step=100,
        )
    positioning = st.text_area(
        "账号定位描述",
        value=existing.get("positioning", ""),
        placeholder="描述该账号的定位、目标人群、内容方向等",
        height=80,
    )
    submitted = st.form_submit_button("保存账号", type="primary")

if submitted:
    if not account_name.strip():
        st.warning("请输入账号名称。")
    else:
        info = {
            "account_name": account_name.strip(),
            "fans_count": fans_count,
            "positioning": positioning.strip(),
        }
        existing_id = st.session_state.aa_account_id
        if existing_id:
            db_utils.update_competitor_account(existing_id, **info)
            st.success(f"已更新账号: {account_name}")
        else:
            new_id = db_utils.save_competitor_account(
                track, info["account_name"], info["fans_count"], info["positioning"]
            )
            st.session_state.aa_account_id = new_id
            st.success(f"已保存账号: {account_name}")
        st.session_state.aa_account_info = info


# ══════════════════════════════════════════
# 第二部分: 笔记输入
# ══════════════════════════════════════════

st.markdown("---")
st.subheader("2. 笔记数据输入")

input_tab1, input_tab2, input_tab3 = st.tabs(["截图上传", "粘贴文本提取", "从流水线导入"])

with input_tab1:
    st.caption("支持三种方式添加截图: Cmd+V 粘贴 / 拖拽图片 / 点击选择文件")
    from utils.paste_capture import render_paste_zone, images_to_vision_input
    captured_images = render_paste_zone(key_prefix="aa_paste")
    if captured_images and st.button("从截图识别笔记", key="btn_extract_img_notes", type="primary"):
        from agents.image_extractor import extract_from_images
        images_bytes = images_to_vision_input(captured_images)
        with st.spinner(f"AI正在识别{len(images_bytes)}张截图..."):
            try:
                structured = extract_from_images(track, images_bytes)
                st.session_state.aa_extracted_notes = structured
                st.session_state.aa_selected_indices = list(range(len(structured)))
                st.success(f"成功识别 {len(structured)} 条笔记!")
            except Exception as e:
                st.error(f"识别失败: {e}")

with input_tab2:
    raw_notes_text = st.text_area(
        "粘贴竞品账号的笔记原始文本(支持一次粘贴多条)",
        height=200,
        placeholder="从小红书App复制笔记内容(标题、正文、点赞数、收藏数等),直接粘贴到这里...",
        key="raw_notes_input",
    )
    if st.button("提取笔记", key="btn_extract_notes", type="primary"):
        if not raw_notes_text.strip():
            st.warning("请先粘贴笔记原始文本。")
        else:
            with st.spinner("正在提取结构化信息..."):
                try:
                    structured = collect_trends(track, raw_notes_text)
                    st.session_state.aa_extracted_notes = structured
                    st.session_state.aa_selected_indices = list(range(len(structured)))
                    st.success(f"成功提取 {len(structured)} 条笔记。")
                except Exception as e:
                    st.error(f"提取失败: {e}")

with input_tab3:
    pipeline_data = st.session_state.pipeline.get("structured_trends")
    if pipeline_data:
        st.info(f"流水线中已有 {len(pipeline_data)} 条结构化笔记,点击下方按钮导入。")
        if st.button("从流水线导入", key="btn_import_pipeline"):
            st.session_state.aa_extracted_notes = pipeline_data
            st.session_state.aa_selected_indices = list(range(len(pipeline_data)))
            st.success(f"已导入 {len(pipeline_data)} 条笔记。")
    else:
        st.info("流水线中暂无数据。请先在「热点选题流水线」页面完成Step1提取,再回来导入。")


# ── 笔记预览与选择 ──

extracted = st.session_state.aa_extracted_notes
if extracted:
    st.markdown(f"**已提取 {len(extracted)} 条笔记** (勾选需要分析的笔记)")

    # 全选/取消按钮行
    col_sel1, col_sel2, _ = st.columns([1, 1, 6])
    with col_sel1:
        if st.button("全选", key="btn_select_all"):
            st.session_state.aa_selected_indices = list(range(len(extracted)))
            st.rerun()
    with col_sel2:
        if st.button("全不选", key="btn_select_none"):
            st.session_state.aa_selected_indices = []
            st.rerun()

    # 笔记表格(带复选框)
    selected = st.session_state.aa_selected_indices or []

    # 构建表头
    header_cols = st.columns([0.5, 3, 1.2, 1, 1, 1, 1, 1.5])
    headers = ["选择", "标题", "类型", "点赞", "评论", "收藏", "转发", "发布日期"]
    for col, header in zip(header_cols, headers):
        col.markdown(f"**{header}**")

    # 显示每条笔记
    new_selected = []
    for i, note in enumerate(extracted):
        is_checked = i in selected
        row_cols = st.columns([0.5, 3, 1.2, 1, 1, 1, 1, 1.5])
        with row_cols[0]:
            if st.checkbox(
                "sel",
                value=is_checked,
                key=f"note_chk_{i}",
                label_visibility="collapsed",
            ):
                new_selected.append(i)
        with row_cols[1]:
            st.text(str(note.get("title", "无标题"))[:40])
        with row_cols[2]:
            st.text(note.get("note_type", "未知"))
        with row_cols[3]:
            st.text(str(note.get("likes", "-")))
        with row_cols[4]:
            st.text(str(note.get("comments", "-")))
        with row_cols[5]:
            st.text(str(note.get("collects", "-")))
        with row_cols[6]:
            st.text(str(note.get("shares", "-")))
        with row_cols[7]:
            st.text(str(note.get("post_date", "-")))

    st.session_state.aa_selected_indices = new_selected


# ══════════════════════════════════════════
# 第三部分: 分析执行与结果展示
# ══════════════════════════════════════════

st.markdown("---")
st.subheader("3. 分析报告")

# 分析按钮
can_analyze = (
    st.session_state.aa_account_info
    and st.session_state.aa_extracted_notes
    and st.session_state.aa_selected_indices
)

if st.button(
    "开始分析",
    key="btn_start_analysis",
    type="primary",
    disabled=not can_analyze,
):
    if not can_analyze:
        st.warning("请先保存账号信息并选择至少一条笔记。")
    else:
        selected_notes = [
            st.session_state.aa_extracted_notes[i]
            for i in st.session_state.aa_selected_indices
        ]
        with st.spinner("正在分析竞品账号,请稍候(通常需要15-30秒)..."):
            try:
                result = analyze_account(
                    track,
                    st.session_state.aa_account_info,
                    selected_notes,
                )
                st.session_state.aa_analysis_result = result
                st.success("分析完成!")
            except Exception as e:
                st.error(f"分析失败: {e}")

if not can_analyze and not st.session_state.aa_analysis_result:
    hints = []
    if not st.session_state.aa_account_info:
        hints.append("保存账号信息")
    if not st.session_state.aa_extracted_notes:
        hints.append("提取或导入笔记数据")
    if st.session_state.aa_extracted_notes and not st.session_state.aa_selected_indices:
        hints.append("勾选至少一条笔记")
    if hints:
        st.info("请先完成: " + " → ".join(hints))


# ── 结果展示 ──

analysis = st.session_state.aa_analysis_result
if analysis:
    cs = analysis.get("computed_stats", {})
    llm = analysis.get("llm_analysis", {})

    # ── 指标卡片行 ──
    st.markdown("#### 核心数据概览")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1:
        st.metric("笔记总数", cs.get("total_notes", 0))
    with m2:
        st.metric("平均点赞", cs.get("avg_likes", 0))
    with m3:
        st.metric("平均评论", cs.get("avg_comments", 0))
    with m4:
        er = cs.get("engagement_rate", 0)
        st.metric("互动率", f"{er}%")
    with m5:
        pf = cs.get("posting_frequency", 0)
        st.metric("发布频率", f"{pf} 条/周")
    with m6:
        td = cs.get("content_type_distribution", {})
        type_summary = " / ".join(f"{k}: {v}" for k, v in td.items() if v > 0)
        st.metric("内容类型", type_summary if type_summary else "-")

    date_range_str = cs.get("date_range", "-")
    trend_info = cs.get("engagement_trend", {})
    trend_dir_map = {"rising": "上升", "stable": "平稳", "declining": "下降"}
    trend_dir = trend_dir_map.get(trend_info.get("direction", ""), "-")
    trend_slope = trend_info.get("slope", 0)
    st.markdown(
        f"**日期范围:** {date_range_str} | "
        f"**互动趋势:** {trend_dir} (斜率: {trend_slope})"
    )

    # ── 图表行1: 饼图 + 折线图 ──
    st.markdown("#### 数据可视化")
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown("**内容类型分布**")
        type_dist = cs.get("content_type_distribution", {})
        type_labels = [k for k, v in type_dist.items() if v > 0]
        type_values = [v for v in type_dist.values() if v > 0]
        if type_labels:
            fig_pie = go.Figure(data=[go.Pie(
                labels=type_labels,
                values=type_values,
                hole=0.35,
                marker=dict(colors=["#FF2442", "#FF6B81", "#FFA5B5"]),
            )])
            fig_pie.update_layout(
                margin=dict(t=20, b=20, l=20, r=20),
                height=350,
                showlegend=True,
            )
            st.plotly_chart(fig_pie, width="stretch")
        else:
            st.info("无内容类型数据。")

    with chart_col2:
        st.markdown("**互动量趋势**")
        # 构建时间序列数据
        selected_notes_for_chart = [
            st.session_state.aa_extracted_notes[i]
            for i in (st.session_state.aa_selected_indices or [])
        ]
        timeline_data = []
        for note in selected_notes_for_chart:
            pd = note.get("post_date")
            if pd:
                total_eng = (
                    (note.get("likes") or 0)
                    + (note.get("comments") or 0)
                    + (note.get("collects") or 0)
                    + (note.get("shares") or 0)
                )
                timeline_data.append({"date": pd, "engagement": total_eng})

        if timeline_data:
            timeline_data.sort(key=lambda x: x["date"])
            fig_line = go.Figure()
            fig_line.add_trace(go.Scatter(
                x=[d["date"] for d in timeline_data],
                y=[d["engagement"] for d in timeline_data],
                mode="lines+markers",
                line=dict(color="#FF2442", width=2),
                marker=dict(size=6),
                name="总互动量",
            ))
            fig_line.update_layout(
                xaxis_title="发布日期",
                yaxis_title="总互动量",
                margin=dict(t=20, b=40, l=40, r=20),
                height=350,
            )
            st.plotly_chart(fig_line, width="stretch")
        else:
            st.info("无日期数据,无法绘制趋势图。")

    # ── 图表行2: 标签柱状图 + 最佳/最差对比 ──
    chart_col3, chart_col4 = st.columns(2)

    with chart_col3:
        st.markdown("**Top 15 话题标签**")
        top_tags = cs.get("top_hashtags", [])
        if top_tags:
            # 反转以便最高的在上面
            tags_reversed = list(reversed(top_tags))
            fig_bar = go.Figure(data=[go.Bar(
                x=[t["count"] for t in tags_reversed],
                y=[t["tag"] for t in tags_reversed],
                orientation="h",
                marker=dict(color="#FF2442"),
            )])
            fig_bar.update_layout(
                xaxis_title="出现次数",
                margin=dict(t=20, b=40, l=120, r=20),
                height=max(350, len(tags_reversed) * 28),
            )
            st.plotly_chart(fig_bar, width="stretch")
        else:
            st.info("无话题标签数据。")

    with chart_col4:
        st.markdown("**最佳 vs 最差笔记**")
        best = cs.get("best_performing_notes", [])
        worst = cs.get("worst_performing_notes", [])
        if best or worst:
            fig_group = go.Figure()

            if best:
                fig_group.add_trace(go.Bar(
                    name="最佳笔记",
                    x=[n["title"][:15] for n in best],
                    y=[n["total_engagement"] for n in best],
                    marker=dict(color="#FF2442"),
                ))
            if worst:
                fig_group.add_trace(go.Bar(
                    name="最差笔记",
                    x=[n["title"][:15] for n in worst],
                    y=[n["total_engagement"] for n in worst],
                    marker=dict(color="#FFA5B5"),
                ))
            fig_group.update_layout(
                barmode="group",
                xaxis_title="笔记",
                yaxis_title="总互动量",
                margin=dict(t=20, b=40, l=40, r=20),
                height=350,
            )
            st.plotly_chart(fig_group, width="stretch")
        else:
            st.info("无笔记互动数据。")

    # ── LLM定性分析 ──
    st.markdown("#### AI 深度分析")

    with st.expander("内容策略分析", expanded=True):
        st.markdown(f"**内容策略:** {llm.get('content_strategy', '-')}")
        st.markdown(f"**定位分析:** {llm.get('positioning_analysis', '-')}")
        st.markdown(f"**增长态势:** {llm.get('growth_assessment', '-')}")

    with st.expander("优势与不足"):
        st.markdown("**优势:**")
        for s in llm.get("strengths", []):
            st.markdown(f"- {s}")
        st.markdown("**不足:**")
        for w in llm.get("weaknesses", []):
            st.markdown(f"- {w}")
        st.markdown(f"**内容空白点:** {llm.get('content_gaps', '-')}")

    with st.expander("可借鉴套路"):
        for i, p in enumerate(llm.get("borrowable_patterns", []), 1):
            st.markdown(f"**套路 {i}:** {p}")

    with st.expander("行动建议"):
        recs = llm.get("actionable_recommendations", [])
        if recs:
            for rec in recs:
                priority = rec.get("priority", "中")
                color_map = {"高": "#FF2442", "中": "#FF9F43", "低": "#2ED573"}
                color = color_map.get(priority, "#999")
                st.markdown(
                    f'<div style="padding: 8px 12px; margin: 6px 0; '
                    f'border-left: 4px solid {color}; background: #f8f9fa;">'
                    f'<strong style="color: {color};">[{priority}]</strong> '
                    f'{rec.get("action", "")}<br>'
                    f'<span style="color: #666; font-size: 0.9em;">'
                    f'{rec.get("rationale", "")}</span></div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("暂无行动建议。")

    # ── 保存分析结果 ──
    st.markdown("---")
    if st.button("保存分析结果", key="btn_save_analysis"):
        account_id = st.session_state.aa_account_id
        if not account_id:
            st.warning("请先保存账号信息。")
        else:
            try:
                # 保存笔记(如果尚未保存)
                existing_notes = db_utils.get_account_notes(account_id)
                if not existing_notes and st.session_state.aa_extracted_notes:
                    for note in st.session_state.aa_extracted_notes:
                        hashtags_val = note.get("hashtags", [])
                        if isinstance(hashtags_val, list):
                            hashtags_val = json.dumps(hashtags_val, ensure_ascii=False)
                        db_utils.save_account_note(
                            account_id=account_id,
                            title=note.get("title", ""),
                            body_text=note.get("body_text", ""),
                            hashtags=hashtags_val,
                            likes=note.get("likes") or 0,
                            comments=note.get("comments") or 0,
                            collects=note.get("collects") or 0,
                            shares=note.get("shares") or 0,
                            post_date=note.get("post_date", ""),
                            note_type=note.get("note_type", "未知"),
                        )

                # 保存分析结果
                db_utils.save_account_analysis(
                    account_id=account_id,
                    computed_stats_json=json.dumps(cs, ensure_ascii=False),
                    llm_analysis_json=json.dumps(llm, ensure_ascii=False),
                    notes_analyzed=len(st.session_state.aa_selected_indices or []),
                )
                st.success("分析结果已保存。")
            except Exception as e:
                st.error(f"保存失败: {e}")
