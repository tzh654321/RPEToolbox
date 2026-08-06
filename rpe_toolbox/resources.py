# -*- coding: utf-8 -*-
"""项目资源路径解析：音频、图标、示例图片均放在 RPET new/assets 下。"""

import os

# 包位于 RPET new/rpe_toolbox，向上两级即项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
AUDIO_DIR = os.path.join(ASSETS_DIR, "audio")
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")
IMAGES_DIR = os.path.join(ASSETS_DIR, "images")


def audio_path(file_name):
    """返回音频文件绝对路径（不存在时仍返回路径，由调用方判断）。"""
    return os.path.join(AUDIO_DIR, file_name)


def find_icon():
    """按优先级返回第一个存在的窗口图标文件，找不到返回 None。"""
    for name in ("ico-z1.png", "ico-z2.png"):
        path = os.path.join(ICONS_DIR, name)
        if os.path.exists(path):
            return path
    return None
