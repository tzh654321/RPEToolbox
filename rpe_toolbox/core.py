# -*- coding: utf-8 -*-
"""主程序公共部分：功能实现已拆分为模组（rpe_toolbox/mods/<功能组>/<模组>.py）。

本文件只保留：
  * FunctionMixin —— 主程序与模组共用的基类（时间换算与缓动来自 easing.EasingMixin）
  * 模组加载：启动时把每个模组的 process 挂成 func_<MOD_KEY>，兼容既有调用名
模组之间不互相调用；模组经常用到的公共函数放在 rpe_toolbox/shared.py。
"""

from . import mods_loader
from .easing import EasingMixin


class FunctionMixin(EasingMixin):
    """功能实现全部来自模组；方法名统一为 func_<MOD_KEY>。"""


# 加载全部模组，并把它们的 process 挂成 FunctionMixin 上的方法
mods_loader.install_legacy_methods(FunctionMixin)
