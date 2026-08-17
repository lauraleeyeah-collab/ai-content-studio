"""Dashboard 统计、最近活动与历史记录删除/清空。"""
from database.connection import get_connection

def get_dashboard_stats() -> dict:
    """返回各功能模块的统计数据,用于Dashboard展示。"""
    stats = {
        "note_analyses_count": 0,
        "competitor_accounts_count": 0,
        "topics_generated_count": 0,
        "copies_generated_count": 0,
        "trend_snapshots_count": 0,
        # AI 超级自媒体工具新模块
        "content_assets_count": 0,
        "publish_records_count": 0,
        "search_keywords_count": 0,
        "channel_rewrites_count": 0,
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
        for table_key, column in (
            ("content_assets_count", "content_assets"),
            ("publish_records_count", "publish_records"),
            ("search_keywords_count", "search_keywords"),
            ("channel_rewrites_count", "channel_rewrites"),
        ):
            try:
                row = conn.execute(f"SELECT COUNT(*) as c FROM {column}").fetchone()
                stats[table_key] = row["c"] if row else 0
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

_CLEARABLE_TABLES = {
    "selected_topics": "选题记录",
    "generated_copy": "文案记录",
    "note_analyses": "笔记分析",
    "competitor_accounts": "竞品账号",
    "trend_snapshots": "趋势分析",
    "title_optimizations": "标题优化",
    "hashtag_recommendations": "标签推荐",
    # AI 超级自媒体工具新模块
    "search_keywords": "搜索词记录",
    "content_assets": "内容资产",
    "channel_rewrites": "渠道改写记录",
    "publish_records": "发布记录",
    "platform_metrics": "平台回填数据",
}

def delete_record(table: str, record_id: int) -> int:
    """按 ID 删除单条记录（表名必须命中白名单）。"""
    if table not in _CLEARABLE_TABLES:
        raise ValueError(f"不允许删除的表: {table}")
    with get_connection() as conn:
        cur = conn.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))
        return cur.rowcount

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
