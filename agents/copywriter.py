"""
Agent 4: 文案生成Agent
根据selected_topic里的content_format,选择图文或视频两套不同的Prompt模板,
最终产出可直接发布的文案/脚本文本。
"""
import json

from prompts import copywriter_prompt
from utils.llm_client import call_llm
from utils.prompt_utils import render
from config import TEMPERATURE_CONFIG


def generate_copy(
    track: str,
    persona_description: str,
    selected_topic: dict,
    viral_structure_reference: dict,
    style_guide: str,
) -> str:
    """
    返回生成的文案/脚本文本(字符串,不是JSON,因为最终产出就是给人看的文案本身)。
    """
    content_format = selected_topic.get("content_format", "图文笔记")
    template = (
        copywriter_prompt.USER_PROMPT_TEMPLATE_VIDEO
        if content_format == "视频笔记"
        else copywriter_prompt.USER_PROMPT_TEMPLATE_IMAGE
    )

    system_prompt = render(copywriter_prompt.SYSTEM_PROMPT, persona_description=persona_description)
    user_prompt = render(
        template,
        track=track or "未指定",
        persona_description=persona_description,
        selected_topic=json.dumps(selected_topic, ensure_ascii=False),
        viral_structure_reference=json.dumps(viral_structure_reference or {}, ensure_ascii=False),
        style_guide=style_guide,
    )
    return call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=TEMPERATURE_CONFIG["copywriter"],
        max_tokens=1500,
    )
