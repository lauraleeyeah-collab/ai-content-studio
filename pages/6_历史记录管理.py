"""
历史记录管理 — 查看/删除所有功能模块生成的历史数据
选题、文案、笔记分析、竞品账号、趋势分析、标题优化、标签推荐
"""
import json
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import db_utils
from utils.ui_components import inject_custom_css, render_metric_card, render_grade_badge

st.set_page_config(page_title="历史记录管理", layout="wide")
inject_custom_css()

db_utils.init_db()

# ── 可管理的记录类型 ──
TYPES = [
    ("selected_topics", "选题记录", "get_selected_topics"),
    ("generated_copy", "文案记录", "get_generated_copies"),
    ("note_analyses", "笔记分析", "get_note_analyses"),
    ("competitor_accounts", "竞品账号", "get_competitor_accounts"),
    ("trend_snapshots", "趋势分析", "get_trend_snapshots"),
    ("title_optimizations", "标题优化", "get_title_optimizations"),
    ("hashtag_recommendations", "标签推荐", "get_hashtag_recommendations"),
]

st.markdown(
    '<div class="page-header"><h1>历史记录管理</h1>'
    "<p>查看、复用或删除各功能模块生成的历史数据，让每次分析结果沉淀为账号运营资产</p></div>",
    unsafe_allow_html=True,
)

# ── 概览统计 ──
stats = db_utils.get_dashboard_stats()
cols = st.columns(4)
with cols[0]:
    render_metric_card("选题记录", stats.get("topics_generated_count", 0), icon="")
with cols[1]:
    render_metric_card("文案记录", stats.get("copies_generated_count", 0), icon="")
with cols[2]:
    render_metric_card("笔记分析", stats.get("note_analyses_count", 0), icon="")
with cols[3]:
    render_metric_card("竞品账号", stats.get("competitor_accounts_count", 0), icon="")

st.markdown("<br>", unsafe_allow_html=True)

# ── 赛道筛选 ──
tracks = set()
for table, _, getter_name in TYPES:
    try:
        for row in getattr(db_utils, getter_name)(limit=200):
            if row.get("track"):
                tracks.add(row["track"])
    except Exception:
        pass
track_options = ["全部"] + sorted(tracks)
filter_track = st.selectbox("按赛道筛选", track_options)

st.markdown("<br>", unsafe_allow_html=True)

tabs = st.tabs([label for _, label, _ in TYPES])

# ══════════════════════════════════════════════
# 通用渲染辅助
# ══════════════════════════════════════════════

def _filtered(rows: list) -> list:
    if filter_track == "全部":
        return rows
    return [r for r in rows if r.get("track") == filter_track]


def _clear_button(table: str, label: str, tab_key: str):
    """带确认步骤的清空按钮，避免误删。"""
    confirm_key = f"confirm_clear_{tab_key}"
    if st.button(f"清空全部{label}", key=f"clear_btn_{tab_key}"):
        st.session_state[confirm_key] = True
    if st.session_state.get(confirm_key):
        st.warning(f"确定要清空所有{label}吗？此操作不可恢复。")
        c1, c2 = st.columns(2)
        if c1.button("确认清空", key=f"clear_yes_{tab_key}"):
            n = db_utils.clear_records(table)
            st.session_state[confirm_key] = False
            st.success(f"已删除 {n} 条{label}。")
            st.rerun()
        if c2.button("取消", key=f"clear_no_{tab_key}"):
            st.session_state[confirm_key] = False
            st.rerun()


# ══════════════════════════════════════════════
# Tab 1: 选题记录
# ══════════════════════════════════════════════
with tabs[0]:
    _clear_button("selected_topics", "选题记录", "topics")
    rows = _filtered(db_utils.get_selected_topics(limit=200))
    if not rows:
        st.info("暂无选题记录。在「热点选题流水线」生成选题后会自动保存到这里。")
    for r in rows:
        with st.expander(f"选题 #{r['id']}｜{r['topic_title']}", expanded=False):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**核心角度**：{r.get('core_angle') or '-'}")
                st.markdown(
                    f"**形式**：{r.get('content_format') or '-'}　"
                    f"**状态**：{r.get('status') or '-'}　"
                    f"**时间**：{r.get('created_at') or '-'}"
                )
            with c2:
                if st.button("删除", key=f"del_topic_{r['id']}"):
                    db_utils.delete_selected_topic(r["id"])
                    st.rerun()

# ══════════════════════════════════════════════
# Tab 2: 文案记录
# ══════════════════════════════════════════════
with tabs[1]:
    _clear_button("generated_copy", "文案记录", "copies")
    rows = _filtered(db_utils.get_generated_copies(limit=200))
    if not rows:
        st.info("暂无文案记录。在「热点选题流水线」生成文案后会自动保存到这里。")
    for r in rows:
        with st.expander(f"文案 #{r['id']}｜{r['topic_title']}", expanded=False):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**形式**：{r.get('content_format') or '-'}　**时间**：{r.get('created_at') or '-'}")
                st.markdown("**全文**：")
                st.code(r.get("copy_text") or "", language="markdown")
            with c2:
                if st.button("删除", key=f"del_copy_{r['id']}"):
                    db_utils.delete_generated_copy(r["id"])
                    st.rerun()

# ══════════════════════════════════════════════
# Tab 3: 笔记分析
# ══════════════════════════════════════════════
with tabs[2]:
    _clear_button("note_analyses", "笔记分析", "notes")
    rows = _filtered(db_utils.get_note_analyses(limit=200))
    if not rows:
        st.info("暂无笔记分析记录。在「笔记爆款分析」完成评分后会自动保存到这里。")
    for r in rows:
        with st.expander(f"笔记分析 #{r['id']}｜{r['note_title']}", expanded=False):
            c1, c2 = st.columns([3, 1])
            with c1:
                render_grade_badge(r.get("grade") or "-")
                st.markdown(
                    f"**总分**：{r.get('total_score')}（50分制）　"
                    f"**类型**：{r.get('note_type') or '-'}　"
                    f"**时间**：{r.get('created_at') or '-'}"
                )
                try:
                    scores = json.loads(r.get("scores_json") or "{}")
                    if scores:
                        st.markdown("**各维度评分**：")
                        for dim, info in scores.items():
                            if isinstance(info, dict) and info.get("score") is not None:
                                st.markdown(f"- {dim}：**{info['score']}** 分 — {info.get('reason', '')[:80]}")
                except (json.JSONDecodeError, TypeError):
                    pass
            with c2:
                if st.button("删除", key=f"del_note_{r['id']}"):
                    db_utils.delete_note_analysis(r["id"])
                    st.rerun()

# ══════════════════════════════════════════════
# Tab 4: 竞品账号
# ══════════════════════════════════════════════
with tabs[3]:
    _clear_button("competitor_accounts", "竞品账号", "accounts")
    rows = _filtered(db_utils.get_competitor_accounts())
    if not rows:
        st.info("暂无竞品账号记录。在「竞品账号分析」保存账号后会自动出现在这里。")
    for r in rows:
        with st.expander(f"竞品账号 #{r['id']}｜{r['account_name']}", expanded=False):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(
                    f"**粉丝**：{r.get('fans_count') or '-'}　"
                    f"**定位**：{r.get('positioning') or '-'}　"
                    f"**赛道**：{r.get('track') or '-'}　"
                    f"**时间**：{r.get('updated_at') or '-'}"
                )
                analyses = db_utils.get_account_analysis_history(r["id"], limit=3)
                if analyses:
                    st.markdown("**最近分析结论**：")
                    for a in analyses:
                        try:
                            llm = json.loads(a.get("llm_analysis_json") or "{}")
                            st.markdown(f"- {a.get('created_at')}：{llm.get('content_strategy', '')[:120]}")
                        except (json.JSONDecodeError, TypeError):
                            pass
            with c2:
                if st.button("删除", key=f"del_account_{r['id']}"):
                    db_utils.delete_competitor_account(r["id"])
                    st.rerun()

# ══════════════════════════════════════════════
# Tab 5: 趋势分析
# ══════════════════════════════════════════════
with tabs[4]:
    _clear_button("trend_snapshots", "趋势分析", "trends")
    rows = _filtered(db_utils.get_trend_snapshots(limit=100))
    if not rows:
        st.info("暂无趋势分析记录。在「热门内容趋势」完成分析后会自动保存到这里。")
    for r in rows:
        with st.expander(f"趋势分析 #{r['id']}｜{r['track']}｜{r.get('time_range')}", expanded=False):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**样本笔记数**：{r.get('notes_count') or '-'}　**时间**：{r.get('created_at') or '-'}")
                try:
                    summary = json.loads(r.get("llm_summary_json") or "{}")
                    if summary.get("dominant_themes"):
                        st.markdown("**主导主题**：" + "、".join(summary["dominant_themes"]))
                    if summary.get("strategic_summary"):
                        st.markdown(f"**战略总结**：{summary['strategic_summary']}")
                except (json.JSONDecodeError, TypeError):
                    pass
            with c2:
                if st.button("删除", key=f"del_trend_{r['id']}"):
                    db_utils.delete_trend_snapshot(r["id"])
                    st.rerun()

# ══════════════════════════════════════════════
# Tab 6: 标题优化
# ══════════════════════════════════════════════
with tabs[5]:
    _clear_button("title_optimizations", "标题优化", "titles")
    rows = _filtered(db_utils.get_title_optimizations(limit=100))
    if not rows:
        st.info("暂无标题优化记录。在「内容创作辅助」优化标题后会自动保存到这里。")
    for r in rows:
        with st.expander(f"标题优化 #{r['id']}｜{r['original_title']}", expanded=False):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**赛道**：{r.get('track') or '-'}　**时间**：{r.get('created_at') or '-'}")
                try:
                    variants = json.loads(r.get("variants_json") or "[]")
                    if variants:
                        st.markdown("**生成变体**：")
                        for i, v in enumerate(variants, 1):
                            if isinstance(v, dict):
                                st.markdown(f"{i}. {v.get('title', '')}（{v.get('formula_type', '')}）")
                            else:
                                st.markdown(f"{i}. {v}")
                except (json.JSONDecodeError, TypeError):
                    pass
            with c2:
                if st.button("删除", key=f"del_title_{r['id']}"):
                    db_utils.delete_title_optimization(r["id"])
                    st.rerun()

# ══════════════════════════════════════════════
# Tab 7: 标签推荐
# ══════════════════════════════════════════════
with tabs[6]:
    _clear_button("hashtag_recommendations", "标签推荐", "hashtags")
    rows = _filtered(db_utils.get_hashtag_recommendations(limit=100))
    if not rows:
        st.info("暂无标签推荐记录。在「内容创作辅助」推荐标签后会自动保存到这里。")
    for r in rows:
        with st.expander(f"标签推荐 #{r['id']}｜{r['note_title']}", expanded=False):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**笔记类型**：{r.get('note_type') or '-'}　**时间**：{r.get('created_at') or '-'}")
                try:
                    recs = json.loads(r.get("recommendations_json") or "{}")
                    tags = recs.get("recommended_hashtags", [])
                    if tags:
                        st.markdown("**推荐标签**：")
                        for t in tags:
                            if isinstance(t, dict):
                                st.markdown(
                                    f"- #{t.get('tag', '')}（{t.get('category', '')}，"
                                    f"相关度 {t.get('relevance_score', '-')}）"
                                )
                    if recs.get("strategy_note"):
                        st.markdown(f"**策略**：{recs['strategy_note']}")
                except (json.JSONDecodeError, TypeError):
                    pass
            with c2:
                if st.button("删除", key=f"del_ht_{r['id']}"):
                    db_utils.delete_hashtag_recommendation(r["id"])
                    st.rerun()
