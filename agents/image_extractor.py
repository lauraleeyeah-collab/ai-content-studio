"""
Agent: 图片/链接内容提取器
使用视觉模型从小红书截图中自动识别笔记内容和互动数据。
"""
import base64

from config import TEMPERATURE_CONFIG
from prompts import image_extraction_prompt
from utils.llm_client import call_llm_with_images_json
from utils.prompt_utils import render


def encode_image_to_base64(image_bytes: bytes, mime_type: str = "image/png") -> dict:
    """将图片字节数据编码为base64格式。"""
    return {
        "type": "base64",
        "data": base64.b64encode(image_bytes).decode("utf-8"),
        "mime": mime_type,
    }


def extract_from_images(track: str, images: list) -> list:
    """
    从一张或多张截图中提取笔记信息。

    Args:
        track: 赛道关键词
        images: 图片列表,每个元素为:
            - base64编码的字符串
            - {"type": "base64", "data": "...", "mime": "image/png"}
            - {"type": "url", "url": "https://..."}
            - bytes(原始图片字节)
            - dict with "bytes" and "mime" keys (Streamlit UploadedFile)

    Returns:
        结构化笔记列表,格式同 Agent 0 (trend_collector) 的输出
    """
    # 统一图片格式
    processed_images = []
    for img in images:
        if isinstance(img, bytes):
            processed_images.append(encode_image_to_base64(img))
        elif isinstance(img, dict):
            if "bytes" in img:
                # Streamlit UploadedFile 格式
                processed_images.append(encode_image_to_base64(img["bytes"], img.get("mime", "image/png")))
            else:
                processed_images.append(img)
        elif isinstance(img, str):
            processed_images.append(img)
        else:
            # 尝试处理为有 read() 方法的对象 (如 UploadedFile)
            try:
                data = img.read() if hasattr(img, "read") else img
                if isinstance(data, bytes):
                    processed_images.append(encode_image_to_base64(data))
                elif hasattr(img, "type"):
                    processed_images.append(encode_image_to_base64(data, img.type))
            except Exception:
                continue

    if not processed_images:
        raise ValueError("没有可用的图片数据")

    user_prompt = render(
        image_extraction_prompt.USER_PROMPT_TEMPLATE,
        track=track or "未指定",
    )

    result = call_llm_with_images_json(
        system_prompt=image_extraction_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        images=processed_images,
        temperature=TEMPERATURE_CONFIG.get("image_extractor", 0.15),
        max_tokens=3000,
    )

    if isinstance(result, dict):
        result = [result]

    if not isinstance(result, list):
        raise ValueError("图片提取Agent返回格式异常,预期是数组")

    return result


def extract_from_url(track: str, url: str) -> list:
    """
    从小红书笔记链接中提取内容。
    使用图片URL方式让视觉模型直接分析页面截图。

    Args:
        track: 赛道关键词
        url: 小红书笔记链接

    Returns:
        结构化笔记列表
    """
    user_prompt = render(
        image_extraction_prompt.USER_PROMPT_TEMPLATE,
        track=track or "未指定",
    )

    # 将URL作为图片源发送给视觉模型
    images = [{"type": "url", "url": url}]

    result = call_llm_with_images_json(
        system_prompt=image_extraction_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        images=images,
        temperature=TEMPERATURE_CONFIG.get("image_extractor", 0.15),
        max_tokens=3000,
    )

    if isinstance(result, dict):
        result = [result]

    if not isinstance(result, list):
        raise ValueError("链接提取Agent返回格式异常,预期是数组")

    return result
