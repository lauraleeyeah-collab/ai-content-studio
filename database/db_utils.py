"""数据库访问层门面。

按领域拆分的模块统一在此导出，保持既有 `db_utils.xxx()` 调用方式不变。
"""

from database.connection import (
    _SCHEMA_PATH,
    get_connection,
    init_db,
    migrate_schema,
)
from database.topics import (
    save_selected_topic,
    get_history_topics,
    get_selected_topics,
    delete_selected_topic,
    get_generated_copies,
    delete_generated_copy,
    save_generated_copy,
    save_style_guide,
    get_latest_style_guide,
)
from database.notes import (
    save_note_analysis,
    get_note_analyses,
    get_note_analysis_by_id,
    delete_note_analysis,
    save_competitor_account,
    update_competitor_account,
    get_competitor_accounts,
    delete_competitor_account,
    get_account_analysis_history,
    save_account_note,
    get_account_notes,
    delete_account_note,
    save_account_analysis,
    get_latest_account_analysis,
    save_trend_snapshot,
    get_trend_snapshots,
    delete_trend_snapshot,
    save_title_optimization,
    get_title_optimizations,
    delete_title_optimization,
    save_hashtag_recommendation,
    get_hashtag_recommendations,
    delete_hashtag_recommendation,
)
from database.metrics import (
    get_dashboard_stats,
    get_recent_activities,
    _CLEARABLE_TABLES,
    delete_record,
    clear_records,
)
from database.channels import (
    save_search_keywords,
    get_search_keywords,
    save_content_asset,
    get_content_assets,
    get_assets_by_topic,
    init_channels,
    get_channels,
    get_channel_rule,
    update_channel_rule,
    save_channel_rewrite,
    get_channel_rewrites,
    save_publish_record,
    get_publish_records,
    update_publish_record,
    save_platform_metric,
    get_platform_metrics,
    get_channel_summary,
    save_topic_to_library,
    update_asset_status,
    get_topic_library,
    search_topic_library,
    delete_asset,
    bulk_import_metrics_csv,
)
from database.personas import (
    save_persona,
    get_personas,
    get_persona,
    set_default_persona,
    delete_persona,
    get_default_persona,
    ensure_default_persona,
)
from database.schedules import (
    save_schedule,
    get_schedules,
    update_schedule_status,
    delete_schedule,
)
