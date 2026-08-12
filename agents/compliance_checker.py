"""
合规检查 Agent（M3 渠道中心）。

双层检查：
1. 代码硬校验（确定性）：红线词表 scan_red_lines + AI 标注要求核对
2. LLM 语义判断：隐含极限词、软广、诱导、答非所问
"""
from prompts import compliance_prompt
from utils.llm_client import call_llm_json
from utils.prompt_utils import render
from utils.rule_checks import scan_red_lines
from config import TEMPERATURE_CONFIG

AI_LABEL_TEMPLATES = {
    "小红书": "本文由 AI 辅助创作",
    "抖音": "本视频含 AI 辅助创作内容",
    "视频号": "本视频由 AI 辅助创作",
    "公众号": "本文由 AI 辅助创作",
    "知乎": "本回答由 AI 辅助创作",
    "问一问": "本回答由 AI 辅助创作",
}


def check_compliance(content: str, channel: str, red_lines: str = "", ai_label_required: bool = True) -> dict:
    """
    双重合规检查。

    返回：
    {
        code_checks: {red_lines(词表硬校验)},
        llm: {llm_findings, ai_label_suggestion, overall_verdict, summary},
        ai_label: {required, template},
        passed: 最终结论（code 词表未命中 且 llm 无 high 风险）
    }
    """
    code_hits = scan_red_lines(content or "")

    user_prompt = render(
        compliance_prompt.USER_PROMPT_TEMPLATE,
        channel=channel,
        red_lines=red_lines or "（无平台自定义红线，按通用红线审核）",
        ai_label_required="是" if ai_label_required else "否",
        content=content or "（空内容）",
    )

    llm = call_llm_json(
        system_prompt=compliance_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["compliance_checker"],
        max_tokens=1500,
    )

    if not isinstance(llm, dict):
        raise ValueError("合规检查返回结果格式异常，预期是对象")

    findings = llm.get("llm_findings") or []
    high_risks = [f for f in findings if f.get("level") == "high"]
    passed = code_hits["passed"] and not high_risks

    return {
        "code_checks": {"red_lines": code_hits},
        "llm": {
            "llm_findings": findings,
            "ai_label_suggestion": llm.get("ai_label_suggestion", ""),
            "overall_verdict": llm.get("overall_verdict", "needs_review"),
            "summary": llm.get("summary", ""),
        },
        "ai_label": {
            "required": bool(ai_label_required),
            "template": AI_LABEL_TEMPLATES.get(channel, "本文由 AI 辅助创作"),
        },
        "passed": passed,
    }
