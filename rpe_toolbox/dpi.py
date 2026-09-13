# -*- coding: utf-8 -*-
"""Windows 高分屏（DPI）支持。

**必须在 import tkinter 之前调用 enable_dpi_awareness()**：
非 DPI 感知进程会被系统按位图插值缩放（界面整体发虚、字体模糊）。
本模块只用 ctypes，不导入 tkinter，因此可以安全地放在最前面执行。

调用顺序见 RPET.py：
    from rpe_toolbox import dpi
    dpi.enable_dpi_awareness()      # 早于任何 tkinter 导入
    ...
    root = tk.Tk()
    dpi.sync_tk_scaling(root)       # 按系统 DPI 校准 Tk 内部缩放因子
"""

import os

# PER_MONITOR_AWARE_V2（-4）：Win10 1703+，窗口跨屏时由系统感知每屏 DPI
_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
# PROCESS_PER_MONITOR_DPI_AWARE（shcore，Win8.1+）
_PROCESS_PER_MONITOR_DPI_AWARE = 2
_LOGPIXELSY = 90
_DEFAULT_DPI = 96.0


def enable_dpi_awareness():
    """启用进程级 DPI 感知，返回是否成功（非 Windows 或已启用时返回 False）。

    三级回退：SetProcessDpiAwarenessContext → shcore.SetProcessDpiAwareness
    → user32.SetProcessDPIAware。设置 RPET_NO_DPI_AWARENESS=1 可跳过（调试用）。
    """
    if os.name != "nt":
        return False
    if os.environ.get("RPET_NO_DPI_AWARENESS"):
        return False

    try:
        import ctypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        func = user32.SetProcessDpiAwarenessContext
        func.argtypes = [ctypes.c_void_p]
        func.restype = ctypes.c_bool
        if func(ctypes.c_void_p(_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)):
            return True
    except Exception:
        pass

    try:
        import ctypes

        shcore = ctypes.WinDLL("shcore", use_last_error=True)
        func = shcore.SetProcessDpiAwareness
        func.argtypes = [ctypes.c_int]
        func.restype = ctypes.c_int
        if func(_PROCESS_PER_MONITOR_DPI_AWARE) == 0:  # S_OK
            return True
    except Exception:
        pass

    try:
        import ctypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        if user32.SetProcessDPIAware():
            return True
    except Exception:
        pass
    return False


def system_dpi():
    """系统 DPI（96 表示 100% 缩放，144 表示 150%）。失败时返回 96。"""
    if os.name != "nt":
        return int(_DEFAULT_DPI)

    try:
        import ctypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        func = user32.GetDpiForSystem  # Win10 1607+
        func.argtypes = []
        func.restype = ctypes.c_uint
        dpi = int(func())
        if dpi > 0:
            return dpi
    except Exception:
        pass

    hdc = None
    try:
        import ctypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        user32.GetDC.argtypes = [ctypes.c_void_p]
        user32.GetDC.restype = ctypes.c_void_p
        user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        hdc = user32.GetDC(None)
        if hdc:
            dpi = int(gdi32.GetDeviceCaps(ctypes.c_void_p(hdc), _LOGPIXELSY))
            if dpi > 0:
                return dpi
    except Exception:
        pass
    finally:
        if hdc:
            try:
                user32.ReleaseDC(None, ctypes.c_void_p(hdc))
            except Exception:
                pass
    return int(_DEFAULT_DPI)


def dpi_scale():
    """系统缩放倍率（100% → 1.0，150% → 1.5）。"""
    return system_dpi() / _DEFAULT_DPI


def sync_tk_scaling(root):
    """按系统 DPI 校准 Tk 内部缩放因子（pixels per point = dpi / 72）。

    Tk 的字体用点（point）指定，若缩放因子仍按 96dpi 计算，高分屏下文字会明显偏小。
    """
    if os.name != "nt":
        return None
    scale = system_dpi() / 72.0
    try:
        root.tk.call("tk", "scaling", scale)
    except Exception:
        return None
    return scale
