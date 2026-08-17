"""
数据中心（M4）— AI 超级自媒体工具

数据回填（手动/CSV）→ 渠道对比看板 → 爆款归因 → 历史管理
归因计算由代码确定性完成（归一化+加权），LLM 只负责解读。
"""
import csv
import io
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import db_utils
from agents.attribution_analyzer import analyze_attribution
from utils.ui_components import inject_custom_css, render_api_key_input
from utils.demo_data import render_demo_toggle, DEMO_METRICS

try:
    import plotly.graph_objects as go
except ImportError:
    go = None

st.set_page_config(page_title="数据中心", layout="wide")
inject_custom_css()

db_utils.init_db()

if "data_center" not in st.session_state:
    st.session_state.data_center = {}

dc = st.session_state.data_center

st.markdown(
    '<div class="page-header"><h1>数据中心</h1>'
    "<p>数据回填 → 渠道对比 → 爆款归因 → 历史管理，发布后用数据反哺下一次生产</p></div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown('<div class="sidebar-header">数据中心配置</div>', unsafe_allow_html=True)
    demo_on = render_demo_toggle()
    render_api_key_input()

tab1, tab2, tab3, tab4 = st.tabs(["① 数据回填", "② 渠道对比", "③ 爆款归因", "④ 历史管理"])

# ══════════════ Tab 1: 数据回填 ══════════════
with tab1:
    st.subheader("数据回填")
    st.caption("发布后手动录入或 CSV 导入各渠道数据（合规优先，不做自动采集）。演示模式可一键填入示例数据。")

    if st.button("一键填入示例渠道数据（演示）", key="btn_dc_fill", type="primary"):
        for m in DEMO_METRICS:
            db_utils.save_platform_metric(
                publish_record_id=0, channel=m["channel"], content_title=m.get("content_title", ""),
                views=m["views"], likes=m["likes"], collects=m["collects"],
                comments=m["comments"], shares=m["shares"],
                play_rate=m["play_rate"], completion_rate=m["completion_rate"],
                collected_at="2026-08-12",
            )
        st.success(f"已回填 {len(DEMO_METRICS)} 条示例数据。")

    st.markdown("**CSV 批量导入：**")
    st.caption("支持列名（中/英均可）：渠道/曝光/点赞/收藏/评论/分享/播放率/完播率/标题/采集日期。")
    csv_file = st.file_uploader("上传回填 CSV", type=["csv"], key="dc_csv_upload")
    if csv_file is not None:
        try:
            raw = csv_file.getvalue().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(raw))
            rows = list(reader)
            if not rows:
                st.warning("CSV 为空。")
            else:
                col_map = {
                    "渠道": "channel", "channel": "channel",
                    "曝光": "views", "views": "views", "播放量": "views",
                    "点赞": "likes", "likes": "likes",
                    "收藏": "collects", "collects": "collects",
                    "评论": "comments", "comments": "comments",
                    "分享": "shares", "shares": "shares",
                    "播放率": "play_rate", "play_rate": "play_rate",
                    "完播率": "completion_rate", "completion_rate": "completion_rate",
                    "标题": "content_title", "content_title": "content_title",
                    "采集日期": "collected_at", "collected_at": "collected_at",
                }
                st.caption(f"识别到 {len(rows)} 行，列：{list(rows[0].keys())}")
                preview = []
                for r in rows[:5]:
                    preview.append({c: r.get(c, "") for c in list(rows[0].keys())[:6]})
                st.dataframe(preview, use_container_width=True)
                if st.button("确认导入", key="btn_dc_csv_import", type="primary"):
                    imported = db_utils.bulk_import_metrics_csv(raw)
                    st.success(f"已批量回填 {imported} 条数据。")
        except Exception as e:
            st.error(f"CSV 解析失败：{e}")

    st.markdown("**手动录入：**")
    with st.form("metric_form"):
        c1, c2 = st.columns(2)
        with c1:
            m_channel = st.selectbox("渠道", ["小红书", "抖音", "视频号", "公众号", "知乎", "问一问"])
            m_title = st.text_input("内容标题", value="")
        with c2:
            m_views = st.number_input("曝光/播放量", min_value=0, value=0, step=100)
            m_date = st.text_input("采集日期", value="2026-08-12")
        m_likes = st.number_input("点赞", min_value=0, value=0, step=1)
        m_collects = st.number_input("收藏", min_value=0, value=0, step=1)
        m_comments = st.number_input("评论", min_value=0, value=0, step=1)
        m_shares = st.number_input("分享", min_value=0, value=0, step=1)
        m_pr = st.number_input("播放率（0-1）", min_value=0.0, max_value=1.0, value=0.0, step=0.01)
        m_cr = st.number_input("完播率（0-1）", min_value=0.0, max_value=1.0, value=0.0, step=0.01)
        submitted = st.form_submit_button("保存回填")
        if submitted:
            rid = db_utils.save_platform_metric(
                publish_record_id=0, channel=m_channel, content_title=m_title or "(未命名)",
                views=int(m_views), likes=int(m_likes), collects=int(m_collects),
                comments=int(m_comments), shares=int(m_shares),
                play_rate=float(m_pr), completion_rate=float(m_cr), collected_at=m_date,
            )
            st.success(f"已保存回填记录（ID {rid}）。")

# ══════════════ Tab 2: 渠道对比 ══════════════
with tab2:
    st.subheader("渠道对比看板")
    summary = db_utils.get_channel_summary()
    if not summary:
        st.info("暂无数据，请先在①回填数据。")
    else:
        st.markdown(f"**共 {sum(s['post_count'] for s in summary)} 条发布记录，覆盖 {len(summary)} 个渠道。**")

        if go is not None:
            names = [s["channel"] for s in summary]
            views = [s["total_views"] for s in summary]
            collect_rate = [round(s["collect_rate"] * 100, 1) for s in summary]
            interaction_rate = [round(s["interaction_rate"] * 100, 1) for s in summary]

            fig = go.Figure()
            fig.add_trace(go.Bar(name="总曝光", x=names, y=views, yaxis="y", marker_color="#FF6B6B"))
            fig.add_trace(go.Bar(name="收藏率%", x=names, y=collect_rate, yaxis="y2", marker_color="#4ECDC4"))
            fig.add_trace(go.Bar(name="互动率%", x=names, y=interaction_rate, yaxis="y2", marker_color="#FFD93D"))
            fig.update_layout(
                title="渠道曝光 vs 收藏率/互动率对比",
                barmode="group",
                yaxis=dict(title="曝光量", side="left"),
                yaxis2=dict(title="比率%", overlaying="y", side="right", range=[0, max(collect_rate + interaction_rate) * 1.2]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("**渠道汇总表：**")
        table = []
        for s in summary:
            table.append({
                "渠道": s["channel"], "发布数": s["post_count"], "总曝光": s["total_views"],
                "平均曝光": s["avg_views"], "收藏率": f"{s['collect_rate']:.1%}",
                "互动率": f"{s['interaction_rate']:.1%}",
                "完播率": f"{s['avg_completion_rate']:.1%}" if s["avg_completion_rate"] else "-",
            })
        st.dataframe(table, use_container_width=True)

# ══════════════ Tab 3: 爆款归因 ══════════════
with tab3:
    st.subheader("爆款归因")
    st.caption("代码计算（归一化+加权排序）→ LLM 解读 → 下一轮生产建议。收藏率权重最高，符合平台趋势。")

    metrics = db_utils.get_platform_metrics()
    if not metrics:
        st.info("暂无数据，请先在①回填数据。")
    else:
        if st.button("执行爆款归因分析", key="btn_dc_attribution", type="primary"):
            with st.spinner("代码计算归因 + AI 解读中..."):
                try:
                    # 按渠道聚合后计算（同一内容跨渠道对比更有意义，此处按内容标题聚合）
                    agg = {}
                    for m in metrics:
                        key = m.get("content_title") or "(未命名)"
                        ch = m.get("channel", "")
                        agg[f"{key}|{ch}"] = {
                            "channel": ch,
                            "views": (agg.get(f"{key}|{ch}", {}).get("views", 0) or 0) + (m.get("views") or 0),
                            "likes": (agg.get(f"{key}|{ch}", {}).get("likes", 0) or 0) + (m.get("likes") or 0),
                            "collects": (agg.get(f"{key}|{ch}", {}).get("collects", 0) or 0) + (m.get("collects") or 0),
                            "comments": (agg.get(f"{key}|{ch}", {}).get("comments", 0) or 0) + (m.get("comments") or 0),
                            "shares": (agg.get(f"{key}|{ch}", {}).get("shares", 0) or 0) + (m.get("shares") or 0),
                            "play_rate": m.get("play_rate") or 0.0,
                            "completion_rate": m.get("completion_rate") or 0.0,
                        }
                    agg_metrics = list(agg.values())
                    result = analyze_attribution("AI工具/自我提升", agg_metrics, "用AI写周报系列内容")
                    dc["attribution"] = result
                    st.success("归因分析完成。")
                except Exception as e:
                    st.error(f"归因分析失败：{e}")

        result = dc.get("attribution")
        if result:
            computed = result.get("computed", {})
            interp = result.get("interpretation")

            st.markdown(f"**最佳渠道：** {computed.get('best_channel')} ｜ **最弱渠道：** {computed.get('worst_channel')}")
            st.markdown(f"**最弱维度：** {computed.get('weakest_dimension') or '无明显短板'} ｜ **样本渠道数：** {computed.get('sample_count')}")

            st.markdown("**渠道综合分排序（确定性计算）：**")
            rows = []
            for c in computed.get("channels", []):
                rows.append({
                    "渠道": c["channel"], "综合分": c["composite"],
                    "收藏率": f"{c['collect_rate']:.1%}", "互动率": f"{c['interaction_rate']:.1%}",
                    "完播率": f"{c['completion_rate']:.1%}" if c["completion_rate"] else "-",
                })
            st.dataframe(rows, use_container_width=True)

            if interp:
                st.markdown("**AI 归因解读：**")
                st.markdown(f"- 最强渠道：{interp.get('top_channel', '-')}")
                st.markdown(f"- 最弱维度：{interp.get('weak_dimension', '-')}")
                st.markdown(f"- 渠道差距：{interp.get('channel_gap', '-')}")
                st.markdown("**下一轮生产建议：**")
                for r in interp.get("recommendations", []):
                    st.markdown(f"- {r}")
                st.caption(f"结论：{interp.get('summary', '')} ｜ 置信度：{interp.get('confidence', '-')}")

# ══════════════ Tab 4: 历史管理 ══════════════
with tab4:
    st.subheader("历史管理")
    st.caption("发布记录与回填数据统一管理，可删除误录数据。")

    records = db_utils.get_publish_records()
    if records:
        st.markdown(f"**发布记录（{len(records)} 条）：**")
        rtable = [{"ID": r["id"], "渠道": r["channel"], "标题": r["final_title"][:24],
                   "状态": r["status"], "计划发布": r["publish_time"]} for r in records]
        st.dataframe(rtable, use_container_width=True)
    else:
        st.caption("暂无发布记录（可在渠道中心生成发布清单后落库）。")

    metrics_list = db_utils.get_platform_metrics(limit=100)
    if metrics_list:
        st.markdown(f"**回填数据（{len(metrics_list)} 条）：**")
        mtable = [{"ID": m["id"], "渠道": m["channel"], "标题": (m["content_title"] or "")[:24],
                   "曝光": m["views"], "收藏": m["collects"], "评论": m["comments"],
                   "采集日": m["collected_at"]} for m in metrics_list]
        st.dataframe(mtable, use_container_width=True)
        del_id = st.number_input("删除回填记录 ID", min_value=1, value=1, step=1)
        if st.button("删除该回填记录", key="btn_dc_delete"):
            with db_utils.get_connection() as conn:
                cur = conn.execute("DELETE FROM platform_metrics WHERE id = ?", (int(del_id),))
            st.success(f"已删除 {cur.rowcount} 条记录。" if cur.rowcount else f"未找到 ID={int(del_id)} 的记录。")
    else:
        st.caption("暂无回填数据。")
