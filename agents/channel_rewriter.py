"""
渠道改写 Agent（M3 渠道中心核心差异化）。

把同一素材按 6 平台规则卡逐一改写，输出版本列表 + 合规检查 + 发布清单。
规则卡来自数据库（可迭代），改写由 LLM 完成，红线与字数由代码校验兜底。

并发改写：多平台改写使用 ThreadPoolExecutor 并行（LLM 调用为 I/O 密集型），
结果按输入顺序返回，单平台失败抛错不静默跳过（保持原有语义）。
"""
from concurrent.futures import ThreadPoolExecutor

from database import db_utils
from database.channel_rules import get_default_rules
from prompts import channel_rewriter_prompt
from utils.llm_client import call_llm_json
from utils.prompt_utils import render
from utils.rule_checks import scan_red_lines
from config import TEMPERATURE_CONFIG

# 全部图文向平台（渠道中心覆盖范围；视频口播在视频工厂，此处改写"视频简介/文案向"）
ALL_CHANNELS = ["小红书", "抖音", "视频号", "公众号", "知乎", "问一问"]

# 并发上限：DashScope qwen-plus 有并发限制，保守取 4
MAX_CONCURRENT_REWRITES = 4


def _get_rule(channel_name: str) -> dict:
    rule = db_utils.get_channel_rule(channel_name)
    if rule:
        return rule
    fallback = next((r for r in get_default_rules() if r["name"] == channel_name), {})
    if not fallback:
        raise ValueError(f"平台规则不存在：{channel_name}")
    return fallback


def rewrite_one_channel(
    title: str,
    source_content: str,
    channel: str,
    search_keywords: list,
    persona_description: str,
) -> dict:
    """单平台改写（供页面单平台操作与测试）。"""
    rule = _get_rule(channel)
    kw_text = "、".join(k.get("keyword", "") for k in (search_keywords or [])[:3])

    user_prompt = render(
        channel_rewriter_prompt.USER_PROMPT_TEMPLATE,
        title=title or "（无标题）",
        source_content=source_content or "（无正文，请根据标题与搜索词展开）",
        search_keywords=kw_text or "无",
        persona_description=persona_description or "未提供",
        channel=channel,
        algorithm_weights=rule.get("algorithm_weights", ""),
        content_prefs=rule.get("content_prefs", ""),
        red_lines=rule.get("red_lines", ""),
        ai_label_required="是" if rule.get("ai_label_required") else "否",
        best_practices=rule.get("best_practices", ""),
    )

    result = call_llm_json(
        system_prompt=channel_rewriter_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["channel_rewriter"],
        max_tokens=2000,
    )

    if not isinstance(result, dict) or not result.get("content"):
        raise ValueError(f"{channel} 渠道改写返回格式异常，缺少 content")

    content = result["content"].strip()
    red_lines = scan_red_lines(content)
    result["code_checks"] = {
        "red_lines": red_lines,
        "has_collect_cta": any(k in content for k in ("建议收藏", "先收藏", "收藏起来")) if channel == "抖音" else None,
    }
    result["ai_label"] = {
        "required": bool(rule.get("ai_label_required")),
        "template": "本文由 AI 辅助创作" if channel != "抖音" else "本视频含 AI 辅助创作内容",
    }
    return result


def rewrite_multi_channel(
    title: str,
    source_content: str,
    channels: list,
    search_keywords: list,
    persona_description: str,
    max_workers: int = None,
) -> list:
    """
    一键多平台改写：对每个目标平台并发调用改写 Agent。

    返回：[{channel, content, rewrite_reasons, publish_tips, code_checks, ai_label}, ...]
    - 结果顺序与输入 channels 顺序一致（便于页面稳定渲染）
    - 单平台失败抛错，不静默跳过（保持原语义）
    - 并发上限取 min(len(channels), MAX_CONCURRENT_REWRITES, max_workers)

    并发策略：LLM 调用为 I/O 密集型，用 ThreadPoolExecutor 即可；
    Demo 模式下返回静态数据，并发同样安全。
    """
    for channel in channels:
        if channel not in ALL_CHANNELS:
            raise ValueError(f"暂不支持渠道：{channel}，可选 {ALL_CHANNELS}")

    # 单平台直接调用，无需线程池开销
    if len(channels) == 1:
        return [rewrite_one_channel(title, source_content, channels[0], search_keywords, persona_description)]

    workers = min(len(channels), MAX_CONCURRENT_REWRITES)
    if max_workers:
        workers = min(workers, max_workers)

    def _do(channel):
        return rewrite_one_channel(title, source_content, channel, search_keywords, persona_description)

    # executor.map 按输入顺序返回结果；任一异常在其对应位置抛出
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="channel-rewrite") as executor:
        return list(executor.map(_do, channels))
