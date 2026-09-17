# -*- coding: utf-8 -*-
"""项目资源路径解析：音频、图标、示例图片、界面文案均放在 RPET new/assets 下。"""

import os
import sys


def _project_root():
    """项目根目录。

    * 开发环境：包上级两级（rpe_toolbox/..）。
    * PyInstaller 打包后：默认取解包目录 _MEIPASS（assets 已随 exe 打包）；
      但如果 **exe 同级**放了 assets 目录，就优先用外部的那份 —— 这样改语言文件、
      功能介绍（assets/lang/mods/）无需重新打包。
    """
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        if os.path.isdir(os.path.join(exe_dir, "assets")):
            return exe_dir
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


PROJECT_ROOT = _project_root()
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
AUDIO_DIR = os.path.join(ASSETS_DIR, "audio")
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")
LANG_DIR = os.path.join(ASSETS_DIR, "lang")


def audio_path(file_name):
    """返回音频文件绝对路径（不存在时仍返回路径，由调用方判断）。"""
    return os.path.join(AUDIO_DIR, file_name)


def lang_path(language_code):
    """返回界面文案文件（assets/lang/<语言代码>.json）的绝对路径。"""
    return os.path.join(LANG_DIR, language_code + ".json")


def lang_mods_dir(language_code):
    """返回功能介绍目录（assets/lang/mods/<语言代码>/<模组key>.json）的绝对路径。

    每个文件是一个 {"text": "..."} 对象，键名为文件名（模组 key）。
    """
    return os.path.join(LANG_DIR, "mods", language_code)


def user_config_path():
    """用户配置（主题等）存放位置：%APPDATA%/RPEToolbox/config.json，无 APPDATA 时放到用户目录。"""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "RPEToolbox", "config.json")


def user_cache_dir():
    """用户级缓存目录：%APPDATA%/RPEToolbox/cache。

    放「需要持久存在、绝不在运行时删除」的派生文件（如由 PNG 转换出的 .ico）。
    与配置文件同一个基目录，便于测试重定向 APPDATA 时一并隔离。

    之所以不用 %TEMP%：临时文件用完即删，而删除动作在带「安全删除」的机器上会把文件
    丢进回收站——每次启动都留 2 个 .ico 的痕迹，用户会看到回收站被项目文件灌满。
    """
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "RPEToolbox", "cache")


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
