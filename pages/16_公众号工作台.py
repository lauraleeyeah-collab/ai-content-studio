"""
公众号工作台 — AI 超级自媒体工具

微信公众号专属生产：选题角度 → 标题 → 头图封面 → 深度长文 → 互动（在看/收藏/留言）。
"""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.platform_workshop_ui import render_platform_workshop

render_platform_workshop("公众号")
