# -*- coding: utf-8 -*-
"""Pillow 可选导入：未安装时 Image / ImageOps 为 None，由调用方给出友好提示。"""

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None
