"""
批量生产编排 Agent（增强）。

一次处理多个选题：每个选题完整跑一遍 M1 图文 → M2 视频 → M3 渠道生产链路，
单条失败不影响其他选题（容错），输出合并报告 Markdown。
"""
import time

from agents.content_report_builder import build_content_report, DEFAULT_CHANNELS


def batch_produce(
    topics: list,
    track: str,
    persona_description: str,
    channels: list = None,
    progress_callback=None,
) -> dict:
    """
    批量生产：对每个选题调用 build_content_report 全流程。

    topics: [{"title", "angle", "content"}, ...]
    progress_callback: 可选回调（done_count, total, current_title），用于 UI 进度条。

    返回：
    {
        results: [{topic_title, status, duration_ms, report} | {topic_title, status: "failed", error}],
        summary: {total, success, failed, total_channel_versions, total_keywords},
        combined_markdown
    }
    """
    channels = channels or DEFAULT_CHANNELS
    results = []
    total = len(topics)
    success = 0
    failed = 0

    for idx, topic in enumerate(topics):
        title = (topic.get("title") or "").strip()
        start = time.time()
        try:
            if not title:
                raise ValueError("选题标题为空")
            report = build_content_report(
                track,
                title,
                topic.get("angle", ""),
                topic.get("content", ""),
                persona_description,
                channels=channels,
            )
            elapsed_ms = int((time.time() - start) * 1000)
            results.append({
                "topic_title": title,
                "status": "success",
                "duration_ms": elapsed_ms,
                "report": report,
            })
            success += 1
        except Exception as e:
            results.append({
                "topic_title": title or "(空标题)",
                "status": "failed",
                "error": str(e)[:200],
            })
            failed += 1

        if progress_callback:
            progress_callback(idx + 1, total, title)

    total_versions = sum(
        len(r["report"].get("channel_versions", [])) for r in results if r["status"] == "success"
    )
    total_keywords = sum(
        len(r["report"].get("search_keywords", [])) for r in results if r["status"] == "success"
    )

    combined = render_combined_markdown(results, track)
    return {
        "results": results,
        "summary": {
            "total": total,
            "success": success,
            "failed": failed,
            "total_channel_versions": total_versions,
            "total_keywords": total_keywords,
        },
        "combined_markdown": combined,
    }


def render_combined_markdown(results: list, track: str = "") -> str:
    """把多条内容报告合并为一个 Markdown（每条一个章节）。"""
    lines = [
        "# 批量内容生产报告",
        "",
        f"**赛道：** {track or '-'}",
        f"**选题数：** {len(results)}",
        "",
    ]
    for i, r in enumerate(results, 1):
        title = r["topic_title"]
        lines.append("")
        lines.append("---")
        lines.append("")
        if r["status"] == "success":
            report = r["report"]
            lines.append(f"## 选题 {i}：{title}")
            lines.append("")
            lines.append(f"**生产耗时：** {r['duration_ms']}ms")
            lines.append(f"**搜索词：** {len(report.get('search_keywords', []))} 个")
            kw = "、".join(k.get("keyword", "") for k in report.get("search_keywords", [])[:3])
            lines.append(f"**Top3：** {kw}")
            lines.append(f"**渠道版本：** {' / '.join(v.get('channel', '') for v in report.get('channel_versions', []))}")
            lines.append("")
            lines.append("### 标题方案")
            for t in report.get("titles", []):
                flag = "✅" if t.get("keyword_check", {}).get("passed") else "⚠️"
                lines.append(f"- {t.get('title')} {flag}")
            lines.append("")
            lines.append("### 图文正文（小红书）")
            lines.append("")
            lines.append(report.get("copy", {}).get("content", ""))
            lines.append("")
            lines.append("### 视频分镜")
            for shot in report.get("script", {}).get("storyboard", []):
                lines.append(
                    f"- `{shot.get('time_start')}s-{shot.get('time_end')}s` {shot.get('voiceover', '')}"
                )
            lines.append("")
            lines.append("### 渠道版本")
            for v in report.get("channel_versions", []):
                lines.append(f"**{v.get('channel')}：** {v.get('content', '')[:80]}…")
            lines.append("")
        else:
            lines.append(f"## 选题 {i}：{title} ❌ 失败")
            lines.append("")
            lines.append(f"错误：{r.get('error', '')}")
            lines.append("")
    return "\n".join(lines)


def parse_bulk_topics(raw_text: str) -> list:
    """
    把多行文本解析为选题列表。支持格式：
    1. 「标题」单独一行（每行一个选题）
    2. 「标题｜角度｜素材」用 | 分隔（素材可省略）
    3. 支持 CSV 三列：标题,角度,素材（自动识别逗号分隔且首行非表头）
    """
    topics = []
    for line in (raw_text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        # 统一全角符号（｜→|，，→,），去掉行首序号（1. / 1、）
        import re
        line = line.replace("｜", "|").replace("，", ",")
        line = re.sub(r"^\d+[.、)\s]+", "", line)
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            topics.append({
                "title": parts[0],
                "angle": parts[1] if len(parts) > 1 else "",
                "content": "|".join(parts[2:]).strip() if len(parts) > 2 else "",
            })
        elif "," in line:
            parts = [p.strip() for p in line.split(",")]
            topics.append({
                "title": parts[0],
                "angle": parts[1] if len(parts) > 1 else "",
                "content": ",".join(parts[2:]).strip() if len(parts) > 2 else "",
            })
        else:
            topics.append({"title": line, "angle": "", "content": ""})
    return topics
