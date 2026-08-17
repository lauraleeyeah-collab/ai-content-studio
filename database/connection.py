"""数据库连接、建表与 Schema 迁移。"""
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
    migrate_schema()

def migrate_schema() -> None:
    """轻量迁移（幂等）：为已存在的表补充新增列。"""
    with get_connection() as conn:
        # content_assets.status
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(content_assets)").fetchall()]
        if "status" not in cols:
            conn.execute("ALTER TABLE content_assets ADD COLUMN status TEXT DEFAULT 'idea'")

        # channels 规则库外置化新增列（旧库补列，新库由 schema.sql 直接建好）
        ch_cols = [r["name"] for r in conn.execute("PRAGMA table_info(channels)").fetchall()]
        if "platform_spec" not in ch_cols:
            conn.execute("ALTER TABLE channels ADD COLUMN platform_spec TEXT")
        if "collect_keywords" not in ch_cols:
            conn.execute("ALTER TABLE channels ADD COLUMN collect_keywords TEXT")
        if "share_keywords" not in ch_cols:
            conn.execute("ALTER TABLE channels ADD COLUMN share_keywords TEXT")
        if "copy_min_words" not in ch_cols:
            conn.execute("ALTER TABLE channels ADD COLUMN copy_min_words INTEGER")
        if "copy_max_words" not in ch_cols:
            conn.execute("ALTER TABLE channels ADD COLUMN copy_max_words INTEGER")
