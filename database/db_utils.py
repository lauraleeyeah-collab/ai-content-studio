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


# ══════════════════════════════════════════════
# AI 超级自媒体工具（M1 图文工厂）
# ══════════════════════════════════════════════

def save_search_keywords(track: str, keywords: list, source_topic: str, channel: str = "小红书") -> int:
    """批量保存搜索词分析结果，返回本次插入条数。"""
    with get_connection() as conn:
        count = 0
        for item in keywords or []:
            conn.execute(
                "INSERT INTO search_keywords (track, keyword, channel, search_intent, priority, source_topic) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    track,
                    item.get("keyword", ""),
                    channel,
                    item.get("search_intent", ""),
                    int(item.get("priority", 5)),
                    source_topic,
                ),
            )
            count += 1
        return count


def get_search_keywords(track: str = None, limit: int = 50) -> list:
    """获取搜索词记录（历史管理用）。"""
    with get_connection() as conn:
        if track:
            rows = conn.execute(
                "SELECT * FROM search_keywords WHERE track = ? ORDER BY created_at DESC LIMIT ?",
                (track, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM search_keywords ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def save_content_asset(
    asset_type: str,
    channel: str,
    title: str,
    content: str,
    search_keywords: str = "",
    persona_name: str = "",
    platform_review: str = "",
) -> int:
    """保存内容资产（选题/图文/脚本/封面提示词统一入口）。"""
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO content_assets (asset_type, channel, title, content, search_keywords, persona_name, platform_review) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (asset_type, channel, title, content, search_keywords, persona_name, platform_review),
        )
        return cur.lastrowid


def get_content_assets(asset_type: str = None, limit: int = 50) -> list:
    """获取内容资产列表。"""
    with get_connection() as conn:
        if asset_type:
            rows = conn.execute(
                "SELECT * FROM content_assets WHERE asset_type = ? ORDER BY created_at DESC LIMIT ?",
                (asset_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM content_assets ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def get_assets_by_topic(topic_title: str, limit: int = 50) -> list:
    """按选题标题模糊查找内容资产（用于历史复用与去重）。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM content_assets WHERE title LIKE ? ORDER BY created_at DESC LIMIT ?",
            (f"%{topic_title}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════
# AI 超级自媒体工具（M3 渠道中心）
# ══════════════════════════════════════════════

def init_channels() -> int:
    """初始化 6 平台规则库（已存在则跳过），返回本次插入条数。"""
    from database.channel_rules import get_default_rules
    inserted = 0
    with get_connection() as conn:
        for rule in get_default_rules():
            exists = conn.execute("SELECT id FROM channels WHERE name = ?", (rule["name"],)).fetchone()
            if exists:
                continue
            conn.execute(
                "INSERT INTO channels (name, algorithm_weights, content_prefs, red_lines, ai_label_required, best_practices) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (rule["name"], rule["algorithm_weights"], rule["content_prefs"],
                 rule["red_lines"], rule["ai_label_required"], rule["best_practices"]),
            )
            inserted += 1
    return inserted


def get_channels() -> list:
    """获取全部平台规则卡。"""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM channels ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def get_channel_rule(channel_name: str) -> dict:
    """按平台名获取规则卡。"""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM channels WHERE name = ?", (channel_name,)).fetchone()
        return dict(row) if row else None


def update_channel_rule(channel_name: str, **fields) -> None:
    """更新平台规则卡的可编辑字段。"""
    allowed = {"algorithm_weights", "content_prefs", "red_lines", "ai_label_required", "best_practices"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    sets = ", ".join(f"{k} = ?" for k in updates)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE channels SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE name = ?",
            (*updates.values(), channel_name),
        )


def save_channel_rewrite(source_asset_id, target_channel, rewritten_content,
                         rewrite_reasons="", compliance_result="") -> int:
    """保存多平台改写版本。"""
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO channel_rewrites (source_asset_id, target_channel, rewritten_content, rewrite_reasons, compliance_result) "
            "VALUES (?, ?, ?, ?, ?)",
            (source_asset_id, target_channel, rewritten_content, rewrite_reasons, compliance_result),
        )
        return cur.lastrowid


def get_channel_rewrites(limit: int = 50) -> list:
    """获取改写版本记录。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM channel_rewrites ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def save_publish_record(asset_id, channel, final_title, final_content,
                        checklist_json="", publish_time="", status="draft") -> int:
    """保存发布记录（发布清单落库）。"""
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO publish_records (asset_id, channel, final_title, final_content, checklist_json, publish_time, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (asset_id, channel, final_title, final_content, checklist_json, publish_time, status),
        )
        return cur.lastrowid


def get_publish_records(limit: int = 100) -> list:
    """获取发布记录（M4 数据中心数据回填的基础）。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM publish_records ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def update_publish_record(record_id: int, **fields) -> None:
    """更新发布记录状态（如：draft → published，供 M4 回填关联）。"""
    allowed = {"status", "publish_time", "final_title", "final_content", "checklist_json"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    sets = ", ".join(f"{k} = ?" for k in updates)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE publish_records SET {sets} WHERE id = ?", (*updates.values(), record_id)
        )


# ══════════════════════════════════════════════
# AI 超级自媒体工具（M4 数据中心）
# ══════════════════════════════════════════════

def save_platform_metric(
    publish_record_id, channel, content_title, views=0, likes=0, collects=0,
    comments=0, shares=0, play_rate=0.0, completion_rate=0.0, collected_at="",
) -> int:
    """保存单条平台数据回填记录。"""
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO platform_metrics (publish_record_id, channel, content_title, views, likes, collects, comments, shares, play_rate, completion_rate, collected_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (publish_record_id, channel, content_title, views, likes, collects,
             comments, shares, play_rate, completion_rate, collected_at),
        )
        return cur.lastrowid


def get_platform_metrics(channel: str = None, limit: int = 200) -> list:
    """获取数据回填记录，支持按渠道过滤。"""
    with get_connection() as conn:
        if channel:
            rows = conn.execute(
                "SELECT * FROM platform_metrics WHERE channel = ? ORDER BY collected_at DESC, id DESC LIMIT ?",
                (channel, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM platform_metrics ORDER BY collected_at DESC, id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def get_channel_summary() -> list:
    """
    渠道汇总（渠道对比看板数据源）：
    按渠道聚合 views/likes/collects/comments/shares 均值与总量，计算互动率。
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT channel,
                   COUNT(*) as post_count,
                   SUM(views) as total_views,
                   SUM(likes) as total_likes,
                   SUM(collects) as total_collects,
                   SUM(comments) as total_comments,
                   SUM(shares) as total_shares,
                   ROUND(AVG(views), 1) as avg_views,
                   ROUND(AVG(collects), 1) as avg_collects,
                   ROUND(AVG(play_rate), 3) as avg_play_rate,
                   ROUND(AVG(completion_rate), 3) as avg_completion_rate
            FROM platform_metrics
            GROUP BY channel
            ORDER BY total_views DESC
            """
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            total_views = d.get("total_views") or 0
            interactions = (d.get("total_likes") or 0) + (d.get("total_collects") or 0) \
                + (d.get("total_comments") or 0) + (d.get("total_shares") or 0)
            d["interaction_rate"] = round(interactions / total_views, 3) if total_views else 0.0
            d["collect_rate"] = round((d.get("total_collects") or 0) / total_views, 3) if total_views else 0.0
            result.append(d)
        return result


# ══════════════════════════════════════════════
# AI 超级自媒体工具（P1 多账号/内容日历）
# ══════════════════════════════════════════════

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
