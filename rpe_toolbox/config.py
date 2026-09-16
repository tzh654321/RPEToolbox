# -*- coding: utf-8 -*-
"""用户配置（主题等）读写：%APPDATA%/RPEToolbox/config.json。

读取优先级：环境变量 RPET_THEME > 配置文件 > 默认主题。
配置读写失败（如目录只读）一律静默降级，不影响程序运行。
"""

import json
import os

from . import resources, theme


def load_config():
    """读取配置字典；文件不存在或损坏时返回空字典。"""
    path = resources.user_config_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_config(config):
    """写入配置；失败返回 False（不抛异常）。"""
    path = resources.user_config_path()
    try:
        directory = os.path.dirname(path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def resolve_theme():
    """按环境变量 > 配置文件 > 默认 的顺序决定启动主题。"""
    env = os.environ.get("RPET_THEME")
    if env:
        return theme.normalize(env)
    configured = load_config().get("theme")
    if configured:
        return theme.normalize(configured)
    return theme.DEFAULT_THEME


def save_theme(name):
    """持久化主题选择。"""
    config = load_config()
    config["theme"] = theme.normalize(name)
    return save_config(config)


def load_setting(key, default=None):
    """读取一项界面设置（功能组 / 语言 / 禁用的模组等）。"""
    return load_config().get(key, default)


def save_setting(key, value):
    """写入一项界面设置。"""
    config = load_config()
    config[key] = value
    return save_config(config)


def resolve_language(default="zh-CN"):
    """启动语言：环境变量 RPET_LANG > 配置 > 默认。"""
    return os.environ.get("RPET_LANG") or load_config().get("language") or default
