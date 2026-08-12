"""
增强功能测试：选题库 CRUD + CSV 批量回填。

运行方式(在项目根目录下):
python -m tests.test_factory_enhance
"""
import os

os.environ["XHS_AGENT_DB_PATH"] = "database/test_enhance.db"

from database import db_utils


def _cleanup():
    with db_utils.get_connection() as conn:
        conn.execute("DELETE FROM content_assets WHERE asset_type = 'topic'")
        conn.execute("DELETE FROM platform_metrics")


def test_topic_library_crud():
    """选题库：新增、重复标题去重更新、状态切换、搜索、删除。"""
    db_utils.init_db()
    _cleanup()

    aid = db_utils.save_topic_to_library("AI工具", "选题A", "角度A", "素材A", status="idea")
    assert aid > 0

    # 同标题再次保存应更新而非重复插入
    aid2 = db_utils.save_topic_to_library("AI工具", "选题A", "新角度", "新素材", status="in_progress")
    assert aid2 == aid, "同标题应复用资产"
    topics = db_utils.get_topic_library()
    assert len(topics) == 1 and topics[0]["status"] == "in_progress"

    # 状态切换
    db_utils.update_asset_status(aid, "published")
    topics = db_utils.get_topic_library()
    assert topics[0]["status"] == "published"

    # 搜索
    found = db_utils.search_topic_library("新角度")
    assert len(found) == 1
    none = db_utils.search_topic_library("不存在的词")
    assert len(none) == 0

    # 删除
    db_utils.delete_asset(aid)
    assert db_utils.get_topic_library() == []
    _cleanup()
    print("test_topic_library_crud 通过")


def test_bulk_import_metrics_csv():
    """CSV 批量回填：中文列名/英文列名/空值容错。"""
    db_utils.init_db()
    _cleanup()

    zh_csv = """渠道,标题,曝光,点赞,收藏,评论,分享,采集日期
小红书,标题A,1000,50,80,10,5,2026-08-12
抖音,标题B,2000,100,150,20,8,2026-08-12
"""
    n1 = db_utils.bulk_import_metrics_csv(zh_csv)
    assert n1 == 2, f"应导入2条,实际{n1}"

    en_csv = "channel,content_title,views,likes,collects,comments,shares\n视频号,标题C,500,30,40,5,2\n"
    n2 = db_utils.bulk_import_metrics_csv(en_csv)
    assert n2 == 1

    # 空值容错 + 播放率/完播率列
    mixed_csv = "渠道,标题,播放率,完播率\n公众号,标题D,0.3,0.2\n"
    n3 = db_utils.bulk_import_metrics_csv(mixed_csv)
    assert n3 == 1

    metrics = db_utils.get_platform_metrics()
    assert len(metrics) == 4
    xhs = next(m for m in metrics if m["channel"] == "小红书")
    assert xhs["views"] == 1000 and xhs["collects"] == 80
    gzh = next(m for m in metrics if m["channel"] == "公众号")
    assert abs(gzh["play_rate"] - 0.3) < 0.001 and abs(gzh["completion_rate"] - 0.2) < 0.001

    _cleanup()
    print("test_bulk_import_metrics_csv 通过")


def test_topic_library_empty_and_invalid():
    """空 CSV 与空选题库边界。"""
    db_utils.init_db()
    _cleanup()
    assert db_utils.bulk_import_metrics_csv("") == 0
    assert db_utils.bulk_import_metrics_csv("渠道,标题\n") == 0, "只有表头无数据应返回0"
    assert db_utils.get_topic_library() == []
    _cleanup()
    print("test_topic_library_empty_and_invalid 通过")


if __name__ == "__main__":
    test_topic_library_crud()
    test_bulk_import_metrics_csv()
    test_topic_library_empty_and_invalid()
    print("\n增强功能全部测试通过!")
