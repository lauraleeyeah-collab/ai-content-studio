"""
P1 功能测试：多账号中心 / 内容日历 / AI 标注自动化。

运行方式(在项目根目录下):
python -m tests.test_factory_p1
"""
import os

os.environ["XHS_AGENT_DB_PATH"] = "database/test_p1.db"

from database import db_utils


def _cleanup():
    with db_utils.get_connection() as conn:
        conn.execute("DELETE FROM personas")
        conn.execute("DELETE FROM publish_schedule")


def test_persona_crud():
    """账号人设：增查、默认切换、幂等种子、删除。"""
    db_utils.init_db()
    _cleanup()

    db_utils.ensure_default_persona()
    personas = db_utils.get_personas()
    assert len(personas) == 1, "首次应种子一个默认人设"
    assert personas[0]["is_default"] == 1

    # 幂等：再次调用不重复插入
    db_utils.ensure_default_persona()
    assert len(db_utils.get_personas()) == 1

    # 新增账号并设为默认
    pid = db_utils.save_persona(name="英语学习号", domain="英语学习", tone="专业+亲和",
                                channels="公众号,知乎", persona_description="人设:英语学习博主")
    db_utils.set_default_persona(pid)
    default = db_utils.get_default_persona()
    assert default["name"] == "英语学习号", f"默认账号应为英语学习号,实际{default['name']}"
    # 只有一个是默认
    assert sum(1 for p in db_utils.get_personas() if p["is_default"]) == 1

    # 删除
    db_utils.delete_persona(pid)
    assert len(db_utils.get_personas()) == 1
    _cleanup()
    print("test_persona_crud 通过")


def test_schedule_crud():
    """内容日历：新增计划、状态更新、查询排序、删除。"""
    db_utils.init_db()
    _cleanup()

    sid1 = db_utils.save_schedule(asset_id=0, channel="小红书", content_title="标题A",
                                  planned_date="2026-08-13", planned_time="20:00", persona_name="深圳搞钱女孩")
    sid2 = db_utils.save_schedule(asset_id=0, channel="抖音", content_title="标题B",
                                  planned_date="2026-08-14", planned_time="12:00", persona_name="深圳搞钱女孩")
    schedules = db_utils.get_schedules()
    assert len(schedules) == 2
    # 按日期排序
    dates = [s["planned_date"] for s in schedules]
    assert dates == sorted(dates), str(dates)

    db_utils.update_schedule_status(sid1, "published")
    updated = [s for s in db_utils.get_schedules() if s["id"] == sid1][0]
    assert updated["status"] == "published"

    db_utils.delete_schedule(sid2)
    assert len(db_utils.get_schedules()) == 1
    _cleanup()
    print("test_schedule_crud 通过")


def test_ai_label_templates():
    """AI 标注模板：覆盖全部 6 个平台。"""
    from agents.compliance_checker import AI_LABEL_TEMPLATES
    for channel in ["小红书", "抖音", "视频号", "公众号", "知乎", "问一问"]:
        template = AI_LABEL_TEMPLATES.get(channel)
        assert template and "AI" in template, f"{channel} 缺标注模板"
    print("test_ai_label_templates 通过")


def test_publish_schedule_link():
    """渠道中心发布清单 → 内容日历联动（每平台一条计划）。"""
    from database import db_utils as du
    du.init_db()
    _cleanup()
    for channel in ["小红书", "抖音", "视频号"]:
        du.save_schedule(asset_id=0, channel=channel, content_title="联动测试",
                         planned_date="2026-08-13", planned_time="20:00", persona_name="深圳搞钱女孩")
    schedules = du.get_schedules()
    channels = {s["channel"] for s in schedules}
    assert channels == {"小红书", "抖音", "视频号"}, str(channels)
    _cleanup()
    print("test_publish_schedule_link 通过")


if __name__ == "__main__":
    test_persona_crud()
    test_schedule_crud()
    test_ai_label_templates()
    test_publish_schedule_link()
    print("\nP1 功能全部测试通过!")
