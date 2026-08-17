"""多账号人设库的数据访问。"""
from database.connection import get_connection

def save_persona(name, domain="", tone="", style_guide_ref="", channels="", persona_description="") -> int:
    """保存账号人设。"""
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO personas (name, domain, tone, style_guide_ref, channels, persona_description) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, domain, tone, style_guide_ref, channels, persona_description),
        )
        return cur.lastrowid

def get_personas() -> list:
    """获取全部账号人设。"""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM personas ORDER BY is_default DESC, id").fetchall()
        return [dict(r) for r in rows]

def get_persona(persona_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM personas WHERE id = ?", (persona_id,)).fetchone()
        return dict(row) if row else None

def set_default_persona(persona_id: int) -> None:
    """设置默认账号人设（同一时间只有一个默认）。"""
    with get_connection() as conn:
        conn.execute("UPDATE personas SET is_default = 0")
        conn.execute("UPDATE personas SET is_default = 1 WHERE id = ?", (persona_id,))

def delete_persona(persona_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM personas WHERE id = ?", (persona_id,))

def get_default_persona() -> dict:
    """获取默认人设；没有默认时返回第一条。"""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM personas WHERE is_default = 1 LIMIT 1").fetchone()
        if row:
            return dict(row)
        row = conn.execute("SELECT * FROM personas ORDER BY id LIMIT 1").fetchone()
        return dict(row) if row else None

def ensure_default_persona() -> None:
    """确保至少有一个账号人设（首次使用预置默认人设，幂等）。"""
    if get_personas():
        return
    seed_desc = (
        "人设:深圳搞钱女孩,定位是借助AI工具辅助工作效率和个人成长,内容覆盖英语学习、阅读、"
        "职场发展、理财、搞钱副业、自律习惯六个方向,内容配比为干货80%+情绪20%。"
        "目标人群:大学生和职场人士,核心诉求是用AI实现自我提升和收入增长。"
    )
    pid = save_persona(
        name="深圳搞钱女孩", domain="AI工具/自我提升", tone="干货80%+情绪20%",
        channels="小红书,抖音,视频号", style_guide_ref="style_samples/style_guide_v2.md",
        persona_description=seed_desc,
    )
    set_default_persona(pid)
