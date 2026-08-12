"""
剪贴板粘贴捕获组件
使用 streamlit-paste-button(基于官方双向通信协议的自定义组件)实现 Cmd+V 粘贴。
之前用 components.html + postMessage 的方案无法工作,因为 components.html 只支持
Python -> 浏览器单向通信,浏览器端拿到的粘贴图片数据永远传不回 Python。
"""
import io

import streamlit as st
from streamlit_paste_button import paste_image_button as pbutton


def render_paste_zone(key_prefix: str = "paste", height: int = 200) -> list:
    """
    渲染一个支持 Cmd+V 粘贴截图的输入区域。

    Args:
        key_prefix: widget key 前缀
        height: 保留参数,兼容旧调用方式(此实现不再需要自定义高度)

    Returns:
        图片列表,每个元素为 {"bytes": bytes, "mime": str, "name": str}
    """
    session_key = f"{key_prefix}_pasted_images"
    if session_key not in st.session_state:
        st.session_state[session_key] = []

    st.caption("点击下方按钮后,先截图(Cmd+Shift+4),再按 Cmd+V 粘贴")

    paste_result = pbutton(
        label="点击后按 Cmd+V 粘贴截图",
        key=f"{key_prefix}_paste_btn",
    )

    if paste_result.image_data is not None:
        img_bytes_io = io.BytesIO()
        paste_result.image_data.save(img_bytes_io, format="PNG")
        img_bytes = img_bytes_io.getvalue()

        already_exists = any(img["bytes"] == img_bytes for img in st.session_state[session_key])
        if not already_exists:
            st.session_state[session_key].append({
                "bytes": img_bytes,
                "mime": "image/png",
                "name": f"pasted_{len(st.session_state[session_key])}.png",
            })

    uploaded = st.file_uploader(
        "或选择本地图片文件",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key=f"{key_prefix}_file_upload",
    )

    upload_session_key = f"{key_prefix}_uploaded_files"
    if upload_session_key not in st.session_state:
        st.session_state[upload_session_key] = []

    if uploaded:
        for f in uploaded:
            f_bytes = f.getvalue()
            already_exists = any(
                img.get("bytes") == f_bytes for img in st.session_state[upload_session_key]
            )
            if not already_exists:
                st.session_state[upload_session_key].append({
                    "bytes": f_bytes,
                    "mime": f.type or "image/png",
                    "name": f.name,
                })

    all_images = list(st.session_state[session_key]) + list(st.session_state[upload_session_key])

    if all_images:
        st.info(f"已添加 {len(all_images)} 张图片")
        cols = st.columns(min(len(all_images), 6))
        for i, img in enumerate(all_images):
            with cols[i % len(cols)]:
                st.image(img["bytes"], width=80)

        if st.button("清除全部图片", key=f"{key_prefix}_clear_btn"):
            st.session_state[session_key] = []
            st.session_state[upload_session_key] = []
            st.rerun()

    return all_images


def images_to_vision_input(images: list) -> list:
    """将图片列表转换为视觉模型输入格式。"""
    result = []
    for img in images:
        if isinstance(img, dict) and "bytes" in img:
            result.append({"bytes": img["bytes"], "mime": img.get("mime", "image/png")})
    return result
