"""笔记爆款分析、竞品账号、趋势快照、标题优化与标签推荐的数据访问。"""
from database.connection import get_connection

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
