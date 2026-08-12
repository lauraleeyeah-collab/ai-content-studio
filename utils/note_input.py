"""
通用笔记输入组件
支持三种输入方式: 截图上传、链接输入、文本粘贴
自动调用视觉模型从截图/链接中提取结构化笔记信息
"""
import json
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.image_extractor import extract_from_images, extract_from_url
from agents.trend_collector import collect_trends


def render_note_input(track: str, key_prefix: str = "note_input") -> list | None:
    """
    渲染通用笔记输入界面,支持截图、链接、文本三种方式。

    Args:
        track: 赛道关键词
        key_prefix: Streamlit widget key前缀,避免多页面key冲突

    Returns:
        结构化笔记列表(同 Agent 0 输出格式), 如果用户未操作则返回 None
    """
    input_mode = st.radio(
        "选择输入方式",
        ["截图上传", "笔记链接", "粘贴文本"],
        horizontal=True,
        key=f"{key_prefix}_mode",
    )

    extracted_notes = None

    if input_mode == "截图上传":
        extracted_notes = _render_image_input(track, key_prefix)

    elif input_mode == "笔记链接":
        extracted_notes = _render_url_input(track, key_prefix)

    else:  # 粘贴文本
        extracted_notes = _render_text_input(track, key_prefix)

    return extracted_notes


def _render_image_input(track: str, key_prefix: str) -> list | None:
    """截图上传输入。支持 Cmd+V 粘贴截图 + 文件拖拽上传。"""
    st.caption("支持三种方式添加截图: Cmd+V 粘贴 / 拖拽图片 / 点击选择文件")

    from utils.paste_capture import render_paste_zone, images_to_vision_input

    captured_images = render_paste_zone(key_prefix=f"{key_prefix}_paste")

    if captured_images and st.button(
        "从截图中提取笔记信息",
        key=f"{key_prefix}_btn_extract_img",
        type="primary",
    ):
        images_bytes = images_to_vision_input(captured_images)

        with st.spinner(f"AI正在识别{len(images_bytes)}张截图中的笔记信息..."):
            try:
                notes = extract_from_images(track, images_bytes)
                st.success(f"成功识别 {len(notes)} 条笔记!")
                _store_in_session(key_prefix, notes)
                return notes
            except Exception as e:
                st.error(f"截图识别失败: {e}")
                return None

    # 检查session中是否有之前的结果
    return _get_from_session(key_prefix)


def _render_url_input(track: str, key_prefix: str) -> list | None:
    """笔记链接输入。"""
    st.caption("输入小红书笔记链接,自动提取内容(注意:部分链接可能因反爬限制无法访问)")

    url_input = st.text_area(
        "笔记链接(每行一个,支持多个)",
        height=100,
        placeholder="https://www.xiaohongshu.com/explore/...\nhttps://www.xiaohongshu.com/discovery/item/...",
        key=f"{key_prefix}_url_input",
    )

    if url_input and st.button(
        "从链接提取笔记信息",
        key=f"{key_prefix}_btn_extract_url",
        type="primary",
    ):
        urls = [u.strip() for u in url_input.strip().split("\n") if u.strip()]
        all_notes = []

        with st.spinner(f"正在从 {len(urls)} 个链接提取笔记信息..."):
            for i, url in enumerate(urls):
                try:
                    notes = extract_from_url(track, url)
                    all_notes.extend(notes)
                except Exception as e:
                    st.warning(f"链接 {i+1} 提取失败: {e}")

        if all_notes:
            st.success(f"成功提取 {len(all_notes)} 条笔记!")
            _store_in_session(key_prefix, all_notes)
            return all_notes
        else:
            st.error("未能从任何链接提取到笔记信息。")
            return None

    return _get_from_session(key_prefix)


def _render_text_input(track: str, key_prefix: str) -> list | None:
    """文本粘贴输入,复用原有的 Agent 0 结构化提取。"""
    st.caption("直接粘贴小红书App中复制的笔记文本,支持一次粘贴多条")

    raw_text = st.text_area(
        "粘贴笔记原始文本",
        height=250,
        placeholder="把从小红书App里复制的标题、正文、点赞收藏数据等直接粘贴进来...",
        key=f"{key_prefix}_text_input",
    )

    if raw_text and st.button(
        "提取并结构化",
        key=f"{key_prefix}_btn_extract_text",
        type="primary",
    ):
        with st.spinner("正在提取结构化信息..."):
            try:
                notes = collect_trends(track, raw_text)
                st.success(f"成功提取 {len(notes)} 条笔记!")
                _store_in_session(key_prefix, notes)
                return notes
            except Exception as e:
                st.error(f"提取失败: {e}")
                return None

    return _get_from_session(key_prefix)


def render_extracted_notes_preview(notes: list, key_prefix: str = "note_input") -> list:
    """
    渲染已提取笔记的预览和编辑界面。

    Returns:
        最终确认的笔记列表(可能经过用户编辑)
    """
    if not notes:
        return notes

    st.write(f"已提取 **{len(notes)}** 条笔记:")

    # JSON编辑区
    edited_json = st.text_area(
        "提取结果(可直接编辑JSON修正,点击保存后生效)",
        value=json.dumps(notes, ensure_ascii=False, indent=2),
        height=300,
        key=f"{key_prefix}_edit_json",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("保存修改", key=f"{key_prefix}_btn_save_edit"):
            try:
                notes = json.loads(edited_json)
                _store_in_session(key_prefix, notes)
                st.success("已保存修改!")
            except json.JSONDecodeError as e:
                st.error(f"JSON格式有误: {e}")

    with col2:
        if st.button("清空重来", key=f"{key_prefix}_btn_clear"):
            _clear_session(key_prefix)
            st.rerun()

    # 简略预览
    for i, n in enumerate(notes[:5]):
        with st.expander(f"{i+1}. {n.get('title', '无标题')}"):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("点赞", n.get("likes") or "-")
            col2.metric("评论", n.get("comments") or "-")
            col3.metric("收藏", n.get("collects") or "-")
            col4.metric("分享", n.get("shares") or "-")
            if n.get("body_text"):
                st.caption(n["body_text"][:200] + "..." if len(n.get("body_text", "")) > 200 else n.get("body_text", ""))
    if len(notes) > 5:
        st.caption(f"...还有 {len(notes) - 5} 条笔记")

    return notes


def _store_in_session(key_prefix: str, notes: list):
    key = f"{key_prefix}_extracted_notes"
    st.session_state[key] = notes


def _get_from_session(key_prefix: str) -> list | None:
    key = f"{key_prefix}_extracted_notes"
    return st.session_state.get(key)


def _clear_session(key_prefix: str):
    key = f"{key_prefix}_extracted_notes"
    if key in st.session_state:
        del st.session_state[key]
