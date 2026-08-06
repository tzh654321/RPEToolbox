# -*- coding: utf-8 -*-
"""rpe 工具箱 —— 模块化包（由原单文件 RPET.py 拆分而来）。

模块划分：
    launcher    pythonw 无窗口重启
    imglib      Pillow 可选导入
    easing      时间数组 / 缓动曲线数学
    core        8 个功能的实现（FunctionMixin）
    resources   资源文件（音频 / 图标）路径解析
    app         RPEToolbox 主类（UI 与流程分发）
"""

from .app import RPEToolbox
from .imglib import Image, ImageOps

__version__ = "2026.7.12"
