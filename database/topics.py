"""选题、生成文案与写作风格语料的数据访问。"""
from database.connection import get_connection

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
