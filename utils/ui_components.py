"""
可复用的 Streamlit UI 组件,避免各页面重复渲染逻辑。
"""
from html import escape
import os

import streamlit as st

try:
    import plotly.graph_objects as go
except ImportError:
    go = None


# ── CSS 注入 ──

def inject_custom_css():
    """加载并注入自定义 CSS,在每个页面顶部调用一次。"""
    css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ── 指标卡片 ──

def render_metric_card(label: str, value, delta: str = None, icon: str = None):
    """
    渲染一个指标卡片。
    label: 指标名称
    value: 指标值(数字或字符串)
    delta: 变化值描述,如"+12%"
    icon: emoji图标
    """
    value_html = escape(str(value), quote=True)
    label_html = escape(label, quote=True)
    icon_html = escape(icon, quote=True) if icon else ""
    delta_html = ""
    if delta:
        css_class = "positive" if delta.startswith("+") else "negative"
        delta_html = f'<div class="metric-delta {css_class}">{escape(delta, quote=True)}</div>'

    html = f"""
    <div class="metric-card">
        {icon_html}
        <div class="metric-value">{value_html}</div>
        <div class="metric-label">{label_html}</div>
        {delta_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ── 等级徽章 ──

def render_grade_badge(grade: str, total_score: float = None):
    """渲染等级圆形徽章(S/A/B/C/D)。"""
    grade_html = escape(grade, quote=True)
    score_text = f"{total_score:.1f}/50" if total_score is not None else ""
    html = f"""
    <div class="text-center">
        <div class="grade-badge grade-{grade_html}">{grade_html}</div>
        <div class="grade-score">{escape(score_text, quote=True)}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ── 评分条 ──

def render_score_bar(label: str, score: float, max_score: int = 10):
    """渲染一条水平评分进度条。"""
    label_html = escape(label, quote=True)
    pct = min(score / max_score * 100, 100)
    html = f"""
    <div class="score-bar-container">
        <div class="score-bar-label">
            <span>{label_html}</span>
            <span class="score-value">{score}/{max_score}</span>
        </div>
        <div class="score-bar">
            <div class="score-bar-fill" style="width: {pct}%"></div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ── 维度评分卡片 ──

# 维度中文名映射
DIMENSION_LABELS = {
    "title_attractiveness": "标题吸引力",
    "cover_appeal": "封面设计",
    "copy_quality": "文案质量",
    "hashtag_strategy": "标签策略",
    "structure_flow": "内容结构",
    "emotion_hook": "情绪触发",
    "interaction_design": "互动引导",
}


def render_dimension_card(dimension_key: str, score_data: dict):
    """
    渲染单个维度评分卡片。
    score_data: {"score": N, "reason": "...", "suggestion": "..."}
    """
    label = escape(DIMENSION_LABELS.get(dimension_key, dimension_key), quote=True)
    score = score_data.get("score", 0)
    reason = escape(score_data.get("reason", ""), quote=True)
    suggestion = escape(score_data.get("suggestion", ""), quote=True)

    suggestion_html = ""
    if suggestion:
        suggestion_html = f'<div class="dim-suggestion">改进建议: {suggestion}</div>'

    html = f"""
    <div class="dimension-card">
        <div class="dim-header">
            <span class="dim-name">{label}</span>
            <span class="dim-score">{score}/10</span>
        </div>
        <div class="dim-reason">{reason}</div>
        {suggestion_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ── 雷达图 ──

def render_radar_chart(scores_dict: dict, title: str = "多维评分"):
    """
    用 Plotly 渲染雷达图。
    scores_dict: {"dimension_key": score, ...} 值为 1-10 的数字
    返回 Plotly Figure,可用 st.plotly_chart() 展示。
    """
    if go is None:
        st.warning("需要安装 plotly 才能显示雷达图: pip install plotly")
        return None

    labels = []
    values = []
    for key, val in scores_dict.items():
        labels.append(DIMENSION_LABELS.get(key, key))
        values.append(val if val is not None else 0)

    # 闭合多边形
    labels.append(labels[0])
    values.append(values[0])

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=labels,
        fill="toself",
        fillcolor="rgba(255, 36, 66, 0.15)",
        line=dict(color="#FF2442", width=2),
        marker=dict(color="#FF2442", size=6),
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 10], tickvals=[2, 4, 6, 8, 10]),
            angularaxis=dict(tickfont=dict(size=12)),
        ),
        showlegend=False,
        title=dict(text=title, font=dict(size=16)),
        margin=dict(t=40, b=20, l=60, r=60),
        height=400,
    )
    return fig


# ── 改进优先级列表 ──

def render_priority_list(items: list):
    """渲染改进优先级标签列表。items: [(维度key, 优先级), ...] 或 [维度key, ...]"""
    html = '<div style="margin: 8px 0;">'
    for i, item in enumerate(items):
        if isinstance(item, (list, tuple)):
            key = item[0]
        else:
            key = item
        label = escape(DIMENSION_LABELS.get(key, key), quote=True)
        if i == 0:
            css_class = "high"
        elif i == 1:
            css_class = "medium"
        else:
            css_class = "low"
        html += f'<span class="priority-tag {css_class}">{label}</span>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


# ── 趋势卡片 ──

def render_trend_card(title: str, content: str, direction: str = "neutral"):
    """
    渲染趋势卡片。
    direction: "up"(兴起) / "down"(衰退) / "neutral"
    """
    css_class = f"trend-{direction}"
    title_html = escape(title, quote=True)
    content_html = escape(content, quote=True)
    html = f"""
    <div class="trend-card {css_class}">
        <div class="trend-title">{title_html}</div>
        <div class="trend-content">{content_html}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ── 判定徽章 ──

def render_verdict_badge(verdict: str):
    """渲染标题判定徽章(推荐/可用/不推荐)。"""
    verdict_html = escape(verdict, quote=True)
    html = f'<span class="verdict-badge verdict-{verdict_html}">{verdict_html}</span>'
    st.markdown(html, unsafe_allow_html=True)


# ── 功能入口卡片 ──

def render_action_card(icon: str, title: str, description: str, page_path: str = None):
    """渲染 Dashboard 功能入口卡片。点击后跳转到指定页面。"""
    if page_path:
        onclick = f"window.parent.location.href = '{escape(page_path, quote=True)}'"
    else:
        onclick = ""
    icon_html = escape(icon, quote=True)
    title_html = escape(title, quote=True)
    desc_html = escape(description, quote=True)

    html = f"""
    <div class="action-card" onclick="{onclick}" style="cursor: pointer;">
        <div class="action-icon">{icon_html}</div>
        <div class="action-title">{title_html}</div>
        <div class="action-desc">{desc_html}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
