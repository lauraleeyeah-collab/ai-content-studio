"""
知乎工作台 — AI 超级自媒体工具

知乎专属生产：选题角度 → 标题 → 头图封面 → 回答正文 → 互动（赞同/收藏/评论）。
"""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.platform_workshop_ui import render_platform_workshop

render_platform_workshop("知乎")
