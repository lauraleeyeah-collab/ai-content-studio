"""搜索词、内容资产、渠道规则、发布记录、平台指标与选题库的数据访问。"""
from database.connection import get_connection

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

def init_channels() -> int:
    """
    初始化 6 平台规则库（已存在则跳过），返回本次插入条数。

    旧库迁移场景：平台行已存在但新字段（platform_spec/collect_keywords 等）为空，
    用种子数据回填，保证规则库外置化后数据完整。
    """
    from database.channel_rules import get_default_rules
    inserted = 0
    backfilled = 0
    with get_connection() as conn:
        for rule in get_default_rules():
            row = conn.execute(
                "SELECT id, platform_spec, collect_keywords, share_keywords, copy_min_words, copy_max_words "
                "FROM channels WHERE name = ?",
                (rule["name"],),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO channels (name, algorithm_weights, content_prefs, red_lines, ai_label_required, "
                    "best_practices, platform_spec, collect_keywords, share_keywords, copy_min_words, copy_max_words) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (rule["name"], rule["algorithm_weights"], rule["content_prefs"],
                     rule["red_lines"], rule["ai_label_required"], rule["best_practices"],
                     rule.get("platform_spec", ""), rule.get("collect_keywords", ""),
                     rule.get("share_keywords", ""), rule.get("copy_min_words"),
                     rule.get("copy_max_words")),
                )
                inserted += 1
                continue
            # 旧库回填：任一新字段为空则补齐（不覆盖用户已编辑的老字段）
            if not row["platform_spec"] or not row["collect_keywords"] or row["copy_min_words"] is None:
                conn.execute(
                    "UPDATE channels SET platform_spec = COALESCE(NULLIF(platform_spec, ''), ?), "
                    "collect_keywords = COALESCE(NULLIF(collect_keywords, ''), ?), "
                    "share_keywords = COALESCE(NULLIF(share_keywords, ''), ?), "
                    "copy_min_words = COALESCE(copy_min_words, ?), "
                    "copy_max_words = COALESCE(copy_max_words, ?) "
                    "WHERE id = ?",
                    (rule.get("platform_spec", ""), rule.get("collect_keywords", ""),
                     rule.get("share_keywords", ""), rule.get("copy_min_words"),
                     rule.get("copy_max_words"), row["id"]),
                )
                backfilled += 1
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
    """更新平台规则卡的可编辑字段（含外置化新增字段）。"""
    allowed = {
        "algorithm_weights", "content_prefs", "red_lines", "ai_label_required", "best_practices",
        "platform_spec", "collect_keywords", "share_keywords", "copy_min_words", "copy_max_words",
    }
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

def save_topic_to_library(track: str, title: str, angle: str = "", content: str = "", status: str = "idea") -> int:
    """保存选题到选题库（内容资产池），重复标题自动更新。"""
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM content_assets WHERE title = ? AND asset_type = 'topic'", (title,)).fetchone()
        if row:
            conn.execute(
                "UPDATE content_assets SET content = ?, platform_review = ?, status = ? WHERE id = ?",
                (content, angle, status, row["id"]),
            )
            return row["id"]
        cur = conn.execute(
            "INSERT INTO content_assets (asset_type, channel, title, content, search_keywords, persona_name, platform_review, status) "
            "VALUES ('topic', ?, ?, ?, ?, ?, ?, ?)",
            (track, title, content, "", "", angle, status),
        )
        return cur.lastrowid

def update_asset_status(asset_id: int, status: str) -> None:
    """更新内容资产状态（idea/in_progress/done/published）。"""
    with get_connection() as conn:
        conn.execute("UPDATE content_assets SET status = ? WHERE id = ?", (status, asset_id))

def get_topic_library(limit: int = 200) -> list:
    """选题库：只取 topic 类型资产，按状态与时间排序。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM content_assets WHERE asset_type = 'topic' "
            "ORDER BY CASE status WHEN 'idea' THEN 0 WHEN 'in_progress' THEN 1 WHEN 'done' THEN 2 ELSE 3 END, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

def search_topic_library(keyword: str, limit: int = 50) -> list:
    """按关键词搜索选题库（标题/角度/内容模糊匹配）。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM content_assets WHERE asset_type = 'topic' AND (title LIKE ? OR content LIKE ? OR platform_review LIKE ?) "
            "ORDER BY id DESC LIMIT ?",
            (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]

def delete_asset(asset_id: int) -> None:
    """删除内容资产（级联清理相关改写与发布记录引用保持简单，直接删资产）。"""
    with get_connection() as conn:
        conn.execute("DELETE FROM content_assets WHERE id = ?", (asset_id,))

def bulk_import_metrics_csv(raw_text: str) -> int:
    """
    批量导入平台回填数据（CSV 文本），支持中英文列名，返回导入条数。
    列名映射：渠道/曝光(播放量)/点赞/收藏/评论/分享/播放率/完播率/标题/采集日期。
    """
    import csv
    import io

    reader = csv.DictReader(io.StringIO(raw_text))
    rows = list(reader)
    if not rows:
        return 0

    def _num(r, key, default=0.0):
        v = (r.get(key) or "").strip()
        if not v:
            return default
        try:
            return float(v)
        except ValueError:
            return default

    imported = 0
    with get_connection() as conn:
        for r in rows:
            channel = (r.get("渠道") or r.get("channel") or "未知").strip()
            title = (r.get("标题") or r.get("content_title") or "(未命名)").strip()
            conn.execute(
                "INSERT INTO platform_metrics (publish_record_id, channel, content_title, views, likes, collects, comments, shares, play_rate, completion_rate, collected_at) "
                "VALUES (0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    channel,
                    title,
                    int(_num(r, "曝光") or _num(r, "views") or _num(r, "播放量")),
                    int(_num(r, "点赞") or _num(r, "likes")),
                    int(_num(r, "收藏") or _num(r, "collects")),
                    int(_num(r, "评论") or _num(r, "comments")),
                    int(_num(r, "分享") or _num(r, "shares")),
                    _num(r, "播放率") or _num(r, "play_rate"),
                    _num(r, "完播率") or _num(r, "completion_rate"),
                    (r.get("采集日期") or r.get("collected_at") or "2026-08-12").strip(),
                ),
            )
            imported += 1
    return imported
