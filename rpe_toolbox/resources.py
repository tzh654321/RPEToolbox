# -*- coding: utf-8 -*-
"""项目资源路径解析：音频、图标、示例图片、界面文案均放在 RPET new/assets 下。"""

import os
import sys


def _project_root():
    """项目根目录：PyInstaller 单文件打包后取解包目录 _MEIPASS，否则取包上级两级。"""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


PROJECT_ROOT = _project_root()
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
AUDIO_DIR = os.path.join(ASSETS_DIR, "audio")
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")
IMAGES_DIR = os.path.join(ASSETS_DIR, "images")
LANG_DIR = os.path.join(ASSETS_DIR, "lang")


def audio_path(file_name):
    """返回音频文件绝对路径（不存在时仍返回路径，由调用方判断）。"""
    return os.path.join(AUDIO_DIR, file_name)


def lang_path(language_code):
    """返回界面文案文件（assets/lang/<语言代码>.json）的绝对路径。"""
    return os.path.join(LANG_DIR, language_code + ".json")


def user_config_path():
    """用户配置（主题等）存放位置：%APPDATA%/RPEToolbox/config.json，无 APPDATA 时放到用户目录。"""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "RPEToolbox", "config.json")


def find_icon():
    """窗口标题栏图标：优先 mini 版（16x16），其次完整版；找不到返回 None。"""
    for name in ("mini ico-z1.png", "ico-z1.png", "ico-z2.png"):
        path = os.path.join(ICONS_DIR, name)
        if os.path.exists(path):
            return path
    return None


def find_full_icon():
    """完整尺寸图标（打包 exe 用），找不到返回 None。"""
    for name in ("ico-z1.png", "ico-z2.png"):
        path = os.path.join(ICONS_DIR, name)
        if os.path.exists(path):
            return path
    return None
