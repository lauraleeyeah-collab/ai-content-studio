"""
封装对阿里云DashScope qwen-plus模型的调用,所有Agent都通过这个模块发起请求,
方便统一更换模型、统一加日志、统一处理JSON解析容错。

使用DashScope的OpenAI兼容模式调用,需要在环境变量里设置DASHSCOPE_API_KEY。
"""
import json
import logging
import os
import re
import time

from config import MODEL_NAME, VISION_MODEL_NAME, DASHSCOPE_BASE_URL

_client = None
logger = logging.getLogger(__name__)

# 稳定运行参数：超时、网络错误重试次数与退避基数
REQUEST_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "60"))
MAX_NETWORK_RETRIES = 3
RETRY_BACKOFF_BASE = 1.5


def _get_client():
    """
    懒加载OpenAI客户端。

    故意不在模块顶部import openai/初始化client,是为了让其他不需要真正调用
    模型的代码(比如离线测试、Agent的纯逻辑校验)可以正常import本模块,
    不会因为没装openai包或没配置API Key就直接报错。
    """
    global _client
    if _client is None:
        from openai import OpenAI

        api_key = os.environ.get("DASHSCOPE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "未检测到环境变量DASHSCOPE_API_KEY,请先在阿里云百炼/DashScope控制台"
                "获取API Key,并设置到环境变量或Streamlit侧边栏的输入框里。"
            )
        _client = OpenAI(api_key=api_key, base_url=DASHSCOPE_BASE_URL, timeout=REQUEST_TIMEOUT)
    return _client


def _call_with_retry(fn, *args, **kwargs):
    """
    调用 OpenAI 客户端方法，对连接/超时/限流/5xx 错误做指数退避重试。
    保持懒加载设计：openai 只在真正调用时导入，离线测试不依赖它。
    """
    import openai

    retryable = (
        openai.APIConnectionError,
        openai.APITimeoutError,
        openai.RateLimitError,
        openai.InternalServerError,
    )
    attempt = 0
    while True:
        try:
            return fn(*args, **kwargs)
        except retryable as exc:
            attempt += 1
            if attempt > MAX_NETWORK_RETRIES:
                logger.error("LLM 调用重试 %d 次后仍失败: %s", MAX_NETWORK_RETRIES, exc)
                raise
            wait = RETRY_BACKOFF_BASE ** attempt
            logger.warning(
                "LLM 调用失败(%s)，%.1fs 后重试 %d/%d",
                type(exc).__name__,
                wait,
                attempt,
                MAX_NETWORK_RETRIES,
            )
            time.sleep(wait)


def call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.5, max_tokens: int = 2000) -> str:
    """
    调用qwen-plus模型,返回原始文本回复(未做任何JSON解析)。
    """
    from utils.demo_data import is_demo_mode, get_demo_response
    if is_demo_mode():
        return get_demo_response(system_prompt, user_prompt)

    client = _get_client()
    logger.info("LLM 调用 model=%s temperature=%s max_tokens=%s", MODEL_NAME, temperature, max_tokens)
    response = _call_with_retry(
        client.chat.completions.create,
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


def extract_json(raw_text: str):
    """
    从模型回复中提取JSON。

    模型有时会规规矩矩只输出JSON,有时会在前后加```json代码块标记,
    偶尔还会多说几句解释性文字。这里按从严到宽依次尝试:
    1. 整段直接解析
    2. 提取```代码块包裹的内容再解析
    3. 兜底:从第一个{或[到最后一个}或]之间截取再解析
    三种方式都失败才抛出异常,交给上层做重试。
    """
    raw_text = raw_text.strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw_text)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass

    start_candidates = [i for i in (raw_text.find("{"), raw_text.find("[")) if i != -1]
    end_candidates = [i for i in (raw_text.rfind("}"), raw_text.rfind("]")) if i != -1]
    if start_candidates and end_candidates:
        start = min(start_candidates)
        end = max(end_candidates) + 1
        snippet = raw_text[start:end]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从模型回复中解析出合法JSON,原始回复前500字:\n{raw_text[:500]}")


def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.5,
    max_tokens: int = 2000,
    max_retries: int = 1,
):
    """
    调用模型并要求返回JSON,自动做解析容错。
    如果第一次解析失败,会在原Prompt后追加纠错提示,重新请求一次(默认重试1次)。
    """
    last_error = None
    prompt = user_prompt
    for _ in range(max_retries + 1):
        raw_text = call_llm(system_prompt, prompt, temperature=temperature, max_tokens=max_tokens)
        try:
            return extract_json(raw_text)
        except ValueError as e:
            last_error = e
            prompt = (
                user_prompt
                + "\n\n你上一次的输出不是合法JSON,请严格只输出合法JSON内容,"
                "不要包含代码块标记```,不要包含任何额外说明文字。"
            )
    raise last_error


def call_llm_with_images(
    system_prompt: str,
    user_prompt: str,
    images: list,
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> str:
    """
    调用视觉模型(qwen-vl-plus),支持传入图片(base64编码或URL)。

    Args:
        system_prompt: 系统提示
        user_prompt: 用户文本提示
        images: 图片列表,每个元素为:
            - base64字符串(自动添加data:image前缀)
            - 或 {"type": "base64", "data": "...", "mime": "image/png"}
            - 或 {"type": "url", "url": "https://..."}
        temperature: 温度参数
        max_tokens: 最大token数

    Returns:
        模型原始文本回复
    """
    from utils.demo_data import is_demo_mode, get_demo_response
    if is_demo_mode():
        return get_demo_response(system_prompt, user_prompt)

    client = _get_client()

    # 构建多模态消息内容
    content_parts = []

    # 先添加图片
    for img in images:
        if isinstance(img, dict):
            if img.get("type") == "url":
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": img["url"]},
                })
            else:
                mime = img.get("mime", "image/png")
                data = img["data"]
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{data}"},
                })
        elif isinstance(img, str):
            # 纯base64字符串,假设是PNG
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img}"},
            })

    # 再添加文本
    content_parts.append({"type": "text", "text": user_prompt})

    logger.info("视觉模型调用 model=%s temperature=%s", VISION_MODEL_NAME, temperature)
    response = _call_with_retry(
        client.chat.completions.create,
        model=VISION_MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content_parts},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


def call_llm_with_images_json(
    system_prompt: str,
    user_prompt: str,
    images: list,
    temperature: float = 0.3,
    max_tokens: int = 2000,
    max_retries: int = 1,
):
    """
    调用视觉模型并要求返回JSON,自动做解析容错和重试。
    """
    last_error = None
    prompt = user_prompt
    for _ in range(max_retries + 1):
        raw_text = call_llm_with_images(system_prompt, prompt, images, temperature, max_tokens)
        try:
            return extract_json(raw_text)
        except ValueError as e:
            last_error = e
            prompt = (
                user_prompt
                + "\n\n你上一次的输出不是合法JSON,请严格只输出合法JSON内容,"
                "不要包含代码块标记```,不要包含任何额外说明文字。"
            )
    raise last_error
