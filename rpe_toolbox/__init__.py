# -*- coding: utf-8 -*-
"""rpe 工具箱 —— 模块化包（由原单文件 RPET.py 拆分而来）。

模块划分：
    launcher    pythonw 无窗口重启
    dpi         Windows 高分屏 DPI 感知（须在 import tkinter 之前调用）
    i18n        界面文案（多语言）加载，文案数据在 assets/lang/*.json
    theme       主题（sv-ttk）与自绘控件配色
    config      用户配置读写（主题记忆等）
    imglib      Pillow 可选导入
    easing      时间数组 / 缓动曲线数学
    core        8 个功能的实现（FunctionMixin）
    resources   资源文件（音频 / 图标 / 文案）路径解析
    app         RPEToolbox 主类（UI 与流程分发）

注意：本文件**不能**在导入时就引入 app（app 会 import tkinter），
否则会抢在 enable_dpi_awareness() 之前引入 tkinter，导致高分屏模糊。
因此 app.RPEToolbox 采用惰性导入（PEP 562）。
"""

import importlib

__version__ = "2026.7.12"

_LAZY_ATTRS = {
    "RPEToolbox": ".app",
    "Image": ".imglib",
    "ImageOps": ".imglib",
}


def __getattr__(name):
    module_name = _LAZY_ATTRS.get(name)
    if module_name is None:
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    value = getattr(importlib.import_module(module_name, __name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(list(globals().keys()) + list(_LAZY_ATTRS.keys()))
