"""
SQLite数据库工具,负责建表和全部的增删查操作。
包含原有流水线功能 + 新增的笔记分析、竞品账号、趋势快照、标题优化、标签推荐等表。
"""
import json
import os
import sqlite3
from contextlib import contextmanager

from config import DB_PATH

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


@contextmanager
def get_connection():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """初始化数据库,建表(如果已存在则跳过,可以重复调用)。"""
    with get_connection() as conn:
        with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())


# ══════════════════════════════════════════════
# 原有流水线功能
# ══════════════════════════════════════════════

def save_selected_topic(track: str, topic_title: str, core_angle: str, content_format: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO selected_topics (track, topic_title, core_angle, content_format) VALUES (?, ?, ?, ?)",
            (track, topic_title, core_angle, content_format),
        )
        return cur.lastrowid


def get_history_topics(track: str, limit: int = 50) -> list:
    """供Agent3做去重判断时使用,返回该赛道下最近发布过的选题。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT topic_title, core_angle, content_format FROM selected_topics "
            "WHERE track = ? ORDER BY created_at DESC LIMIT ?",
            (track, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_selected_topics(track: str = None, limit: int = 50) -> list:
    """获取选题记录列表（历史记录管理页用）。"""
    with get_connection() as conn:
        if track:
            rows = conn.execute(
                "SELECT * FROM selected_topics WHERE track = ? ORDER BY created_at DESC LIMIT ?",
                (track, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM selected_topics ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def delete_selected_topic(topic_id: int) -> None:
    """删除选题及其关联的生成文案。"""
    with get_connection() as conn:
        conn.execute("DELETE FROM generated_copy WHERE topic_id = ?", (topic_id,))
        conn.execute("DELETE FROM selected_topics WHERE id = ?", (topic_id,))


def get_generated_copies(limit: int = 50) -> list:
    """获取文案记录列表，关联选题标题（历史记录管理页用）。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT c.id, c.topic_id, c.content_format, c.copy_text, c.created_at, "
            "       COALESCE(t.topic_title, '(选题已删除)') as topic_title "
            "FROM generated_copy c LEFT JOIN selected_topics t ON c.topic_id = t.id "
            "ORDER BY c.created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_generated_copy(copy_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM generated_copy WHERE id = ?", (copy_id,))


def save_generated_copy(topic_id: int, content_format: str, copy_text: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO generated_copy (topic_id, content_format, copy_text) VALUES (?, ?, ?)",
            (topic_id, content_format, copy_text),
        )
        return cur.lastrowid


def save_style_guide(version: str, content: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO style_corpus (version, content) VALUES (?, ?)",
            (version, content),
        )


def get_latest_style_guide() -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT content FROM style_corpus ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return row["content"] if row else None


# ══════════════════════════════════════════════
# Dashboard 统计
# ══════════════════════════════════════════════

def get_dashboard_stats() -> dict:
    """返回各功能模块的统计数据,用于Dashboard展示。"""
    stats = {
        "note_analyses_count": 0,
        "competitor_accounts_count": 0,
        "topics_generated_count": 0,
        "copies_generated_count": 0,
        "trend_snapshots_count": 0,
    }
    with get_connection() as conn:
        try:
            row = conn.execute("SELECT COUNT(*) as c FROM note_analyses").fetchone()
            stats["note_analyses_count"] = row["c"] if row else 0
        except Exception:
            pass
        try:
            row = conn.execute("SELECT COUNT(*) as c FROM competitor_accounts").fetchone()
            stats["competitor_accounts_count"] = row["c"] if row else 0
        except Exception:
            pass
        try:
            row = conn.execute("SELECT COUNT(*) as c FROM selected_topics").fetchone()
            stats["topics_generated_count"] = row["c"] if row else 0
        except Exception:
            pass
        try:
            row = conn.execute("SELECT COUNT(*) as c FROM generated_copy").fetchone()
            stats["copies_generated_count"] = row["c"] if row else 0
        except Exception:
            pass
        try:
            row = conn.execute("SELECT COUNT(*) as c FROM trend_snapshots").fetchone()
            stats["trend_snapshots_count"] = row["c"] if row else 0
        except Exception:
            pass
    return stats


def get_recent_activities(limit: int = 10) -> list:
    """获取最近的操作记录,跨多张表按时间倒序合并。"""
    activities = []
    with get_connection() as conn:
        # 笔记分析
        try:
            rows = conn.execute(
                "SELECT created_at, note_title as title, grade as detail, 'note_analysis' as type "
                "FROM note_analyses ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            for r in rows:
                activities.append(dict(r))
        except Exception:
            pass
        # 选题生成
        try:
            rows = conn.execute(
                "SELECT created_at, topic_title as title, content_format as detail, 'topic' as type "
                "FROM selected_topics ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            for r in rows:
                activities.append(dict(r))
        except Exception:
            pass
        # 文案生成
        try:
            rows = conn.execute(
                "SELECT created_at, content_format as title, '' as detail, 'copy' as type "
                "FROM generated_copy ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            for r in rows:
                activities.append(dict(r))
        except Exception:
            pass
        # 趋势分析
        try:
            rows = conn.execute(
                "SELECT created_at, track as title, time_range as detail, 'trend' as type "
                "FROM trend_snapshots ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            for r in rows:
                activities.append(dict(r))
        except Exception:
            pass

    # 按时间倒序排序并截断
    activities.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return activities[:limit]


# ══════════════════════════════════════════════
# 笔记爆款分析
# ══════════════════════════════════════════════

def save_note_analysis(
    track: str, note_title: str, note_type: str,
    scores_json: str, total_score: float, grade: str,
    improvement_priorities: str, raw_input_json: str,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO note_analyses "
            "(track, note_title, note_type, scores_json, total_score, grade, improvement_priorities, raw_input_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (track, note_title, note_type, scores_json, total_score, grade, improvement_priorities, raw_input_json),
        )
        return cur.lastrowid


def get_note_analyses(track: str = None, limit: int = 20) -> list:
    with get_connection() as conn:
        if track:
            rows = conn.execute(
                "SELECT * FROM note_analyses WHERE track = ? ORDER BY created_at DESC LIMIT ?",
                (track, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM note_analyses ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def get_note_analysis_by_id(analysis_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM note_analyses WHERE id = ?", (analysis_id,)
        ).fetchone()
        return dict(row) if row else None


def delete_note_analysis(analysis_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM note_analyses WHERE id = ?", (analysis_id,))


# ══════════════════════════════════════════════
# 竞品账号分析
# ══════════════════════════════════════════════

def save_competitor_account(track: str, account_name: str, fans_count: int, positioning: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO competitor_accounts (track, account_name, fans_count, positioning) VALUES (?, ?, ?, ?)",
            (track, account_name, fans_count, positioning),
        )
        return cur.lastrowid


def update_competitor_account(account_id: int, **kwargs) -> None:
    if not kwargs:
        return
    allowed = {"account_name", "fans_count", "positioning"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [account_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE competitor_accounts SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            values,
        )


def get_competitor_accounts(track: str = None) -> list:
    with get_connection() as conn:
        if track:
            rows = conn.execute(
                "SELECT * FROM competitor_accounts WHERE track = ? ORDER BY updated_at DESC", (track,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM competitor_accounts ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def delete_competitor_account(account_id: int) -> None:
    """删除竞品账号及其关联笔记和分析结果（依赖外键级联，手动清一遍更稳妥）。"""
    with get_connection() as conn:
        conn.execute("DELETE FROM account_notes WHERE account_id = ?", (account_id,))
        conn.execute("DELETE FROM account_analyses WHERE account_id = ?", (account_id,))
        conn.execute("DELETE FROM competitor_accounts WHERE id = ?", (account_id,))


def get_account_analysis_history(account_id: int, limit: int = 20) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM account_analyses WHERE account_id = ? ORDER BY created_at DESC LIMIT ?",
            (account_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def save_account_note(
    account_id: int, title: str, body_text: str, hashtags: str,
    likes: int, comments: int, collects: int, shares: int,
    post_date: str, note_type: str,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO account_notes "
            "(account_id, title, body_text, hashtags, likes, comments, collects, shares, post_date, note_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (account_id, title, body_text, hashtags, likes, comments, collects, shares, post_date, note_type),
        )
        return cur.lastrowid


def get_account_notes(account_id: int) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM account_notes WHERE account_id = ? ORDER BY post_date DESC", (account_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def delete_account_note(note_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM account_notes WHERE id = ?", (note_id,))


def save_account_analysis(
    account_id: int, computed_stats_json: str, llm_analysis_json: str, notes_analyzed: int,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO account_analyses "
            "(account_id, computed_stats_json, llm_analysis_json, notes_analyzed) "
            "VALUES (?, ?, ?, ?)",
            (account_id, computed_stats_json, llm_analysis_json, notes_analyzed),
        )
        return cur.lastrowid


def get_latest_account_analysis(account_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM account_analyses WHERE account_id = ? ORDER BY created_at DESC LIMIT 1",
            (account_id,),
        ).fetchone()
        return dict(row) if row else None


# ══════════════════════════════════════════════
# 趋势分析
# ══════════════════════════════════════════════

def save_trend_snapshot(
    track: str, time_range: str, notes_count: int,
    computed_stats_json: str, llm_summary_json: str,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO trend_snapshots "
            "(track, time_range, notes_count, computed_stats_json, llm_summary_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (track, time_range, notes_count, computed_stats_json, llm_summary_json),
        )
        return cur.lastrowid


def get_trend_snapshots(track: str = None, limit: int = 10) -> list:
    with get_connection() as conn:
        if track:
            rows = conn.execute(
                "SELECT * FROM trend_snapshots WHERE track = ? ORDER BY created_at DESC LIMIT ?",
                (track, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM trend_snapshots ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def delete_trend_snapshot(snapshot_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM trend_snapshots WHERE id = ?", (snapshot_id,))


# ══════════════════════════════════════════════
# 标题优化
# ══════════════════════════════════════════════

def save_title_optimization(track: str, original_title: str, topic_context: str, variants_json: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO title_optimizations (track, original_title, topic_context, variants_json) "
            "VALUES (?, ?, ?, ?)",
            (track, original_title, topic_context, variants_json),
        )
        return cur.lastrowid


def get_title_optimizations(track: str = None, limit: int = 10) -> list:
    with get_connection() as conn:
        if track:
            rows = conn.execute(
                "SELECT * FROM title_optimizations WHERE track = ? ORDER BY created_at DESC LIMIT ?",
                (track, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM title_optimizations ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def delete_title_optimization(opt_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM title_optimizations WHERE id = ?", (opt_id,))


# ══════════════════════════════════════════════
# 标签推荐
# ══════════════════════════════════════════════

def save_hashtag_recommendation(track: str, note_title: str, note_type: str, recommendations_json: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO hashtag_recommendations (track, note_title, note_type, recommendations_json) "
            "VALUES (?, ?, ?, ?)",
            (track, note_title, note_type, recommendations_json),
        )
        return cur.lastrowid


def get_hashtag_recommendations(track: str = None, limit: int = 10) -> list:
    with get_connection() as conn:
        if track:
            rows = conn.execute(
                "SELECT * FROM hashtag_recommendations WHERE track = ? ORDER BY created_at DESC LIMIT ?",
                (track, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM hashtag_recommendations ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def delete_hashtag_recommendation(rec_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM hashtag_recommendations WHERE id = ?", (rec_id,))


# ══════════════════════════════════════════════
# 历史记录管理
# ══════════════════════════════════════════════

# 允许被"清空"操作的表（白名单，防止误删其它表）
_CLEARABLE_TABLES = {
    "selected_topics": "选题记录",
    "generated_copy": "文案记录",
    "note_analyses": "笔记分析",
    "competitor_accounts": "竞品账号",
    "trend_snapshots": "趋势分析",
    "title_optimizations": "标题优化",
    "hashtag_recommendations": "标签推荐",
}


def clear_records(table: str) -> int:
    """清空指定类型的历史记录，返回删除条数。表名必须命中白名单。"""
    if table not in _CLEARABLE_TABLES:
        raise ValueError(f"不允许清空的表: {table}")
    with get_connection() as conn:
        if table == "competitor_accounts":
            conn.execute("DELETE FROM account_notes")
            conn.execute("DELETE FROM account_analyses")
        cur = conn.execute(f"DELETE FROM {table}")
        return cur.rowcount
