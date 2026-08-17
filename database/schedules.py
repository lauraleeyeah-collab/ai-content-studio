"""内容日历（发布计划）的数据访问。"""
from database.connection import get_connection

def save_schedule(asset_id, channel, content_title, planned_date, planned_time, persona_name="", notes="") -> int:
    """保存发布计划（内容日历数据源）。"""
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO publish_schedule (asset_id, channel, content_title, planned_date, planned_time, persona_name, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (asset_id, channel, content_title, planned_date, planned_time, persona_name, notes),
        )
        return cur.lastrowid

def get_schedules(limit: int = 200) -> list:
    """获取发布计划，按计划时间排序。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM publish_schedule ORDER BY planned_date, planned_time LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

def update_schedule_status(schedule_id: int, status: str) -> None:
    """更新发布计划状态（planned/published/skipped）。"""
    with get_connection() as conn:
        conn.execute("UPDATE publish_schedule SET status = ? WHERE id = ?", (status, schedule_id))

def delete_schedule(schedule_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM publish_schedule WHERE id = ?", (schedule_id,))
