# -*- coding: utf-8 -*-
"""主程序公共部分：供各模组共同调用的辅助函数。

模组之间不互相调用；一个函数被多个模组用到时（例如"切割密度"输入行），就放到这里。
"""

from rpe_toolbox.i18n import t


def density_of(app, value=None):
    """取切割密度：优先用显式传入的值（内部/测试调用），否则读界面上当前页的输入框。"""
    if value is not None:
        try:
            return int(value)
        except (TypeError, ValueError):
            pass
    try:
        return int(app.density_var.get())
    except (AttributeError, TypeError, ValueError):
        return 16


def density_row(app, parent):
    """切割密度输入行（非线性切割与极坐标转换两个模组共用）。"""
    import tkinter as tk
    from tkinter import ttk

    row = ttk.Frame(parent)
    row.pack(fill=tk.X, pady=app.px(2))
    ttk.Label(row, text=t("labels.density")).pack(side=tk.LEFT, padx=app.px(5))
    ttk.Entry(row, textvariable=app.density_var, width=10).pack(side=tk.LEFT, padx=app.px(5))
    return row
