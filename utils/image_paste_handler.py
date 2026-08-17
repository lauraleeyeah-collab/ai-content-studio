"""
图像粘贴处理器
提供在Streamlit文本输入框中粘贴图片的功能
"""

import base64
import streamlit as st


def render_image_paste_input(label, key, height=150):
    """
    渲染一个支持粘贴图片的输入区域

    Args:
        label: 输入框标签
        key: 组件唯一标识
        height: 输入区域高度

    Returns:
        tuple: (text_content, images_list)
    """

    # 初始化session state
    if f"{key}_images" not in st.session_state:
        st.session_state[f"{key}_images"] = []
    if f"{key}_text" not in st.session_state:
        st.session_state[f"{key}_text"] = ""

    st.markdown(f"#### {label}")

    # 创建两列布局：左侧为文本输入，右侧为图片预览
    col1, col2 = st.columns([2, 1])

    with col1:
        # 文本输入区域
        text_content = st.text_area(
            "文本内容",
            value=st.session_state[f"{key}_text"],
            key=f"{key}_textarea",
            height=height
        )
        st.session_state[f"{key}_text"] = text_content

        # 粘贴区域
        st.markdown("##### 粘贴图片")
        st.caption("支持三种方式添加图片: Cmd+V 粘贴 / 拖拽图片 / 点击选择文件")

        # 使用现有的粘贴组件
        from utils.paste_capture import render_paste_zone
        captured_images = render_paste_zone(key_prefix=key)

        # 更新session state中的图片
        if captured_images:
            st.session_state[f"{key}_images"] = captured_images

    with col2:
        # 图片预览区域
        st.markdown("##### 图片预览")
        images = st.session_state[f"{key}_images"]

        if images:
            for i, img in enumerate(images):
                # 显示图片预览
                if isinstance(img, dict) and "bytes" in img:
                    st.image(img["bytes"], caption=f"图片 {i+1}", use_column_width=True)
                elif isinstance(img, dict) and "data" in img:
                    # Base64数据
                    try:
                        img_bytes = base64.b64decode(img["data"])
                        st.image(img_bytes, caption=f"图片 {i+1}", use_column_width=True)
                    except Exception:
                        st.warning(f"无法显示图片 {i+1}")

                # 删除按钮
                if st.button(f"删除图片 {i+1}", key=f"{key}_del_{i}"):
                    st.session_state[f"{key}_images"].pop(i)
                    st.rerun()
        else:
            st.info("暂无图片")

    return text_content, images


def get_image_input_state(key):
    """
    获取图像输入的状态

    Args:
        key: 组件唯一标识

    Returns:
        tuple: (text_content, images_list)
    """
    text_content = st.session_state.get(f"{key}_text", "")
    images = st.session_state.get(f"{key}_images", [])
    return text_content, images


def clear_image_input(key):
    """
    清除图像输入内容

    Args:
        key: 组件唯一标识
    """
    if f"{key}_text" in st.session_state:
        del st.session_state[f"{key}_text"]
    if f"{key}_images" in st.session_state:
        del st.session_state[f"{key}_images"]