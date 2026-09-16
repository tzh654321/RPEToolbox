# -*- coding: utf-8 -*-
"""模组：全谱切割合并

所属功能组：全谱处理
MOD_KEY 与 assets/lang/*.json 里 functions[].key 对应；序号由主程序加载时决定，本文件不写序号。

暂时通过调用外部 "RPE Event Cutter V1.4.exe" 实现：输入 zip/pez/文件夹，输出 pez 文件（而不是 json 片段），
以后可能用 python 重构。外部程序缺失或调用失败时给出明确提示，不影响其它模组。
"""

import os
import subprocess

from rpe_toolbox.i18n import t

MOD_KEY = "score_cut_merge"
MOD_ORDER = 10

CUTTER_PATH = r"D:\Download\RPE Event Cutter V1.4.exe"


def build_options(app, parent):
    """输入（zip/pez/文件夹）+ 输出 pez 路径。"""
    from tkinter import filedialog, ttk
    import tkinter as tk

    app.cutter_input_var = tk.StringVar()
    app.cutter_output_var = tk.StringVar()

    row_in = ttk.Frame(parent)
    row_in.pack(fill=tk.X, pady=app.px(2))
    ttk.Label(row_in, text=t("labels.input_path")).pack(side=tk.LEFT, padx=app.px(5))
    ttk.Entry(row_in, textvariable=app.cutter_input_var).pack(side=tk.LEFT, fill=tk.X,
                                                             expand=True, padx=app.px(5))
    ttk.Button(row_in, text=t("labels.browse_input"),
               command=lambda: choose_input(app)).pack(side=tk.LEFT, padx=app.px(5))

    row_out = ttk.Frame(parent)
    row_out.pack(fill=tk.X, pady=app.px(2))
    ttk.Label(row_out, text=t("labels.output_path")).pack(side=tk.LEFT, padx=app.px(5))
    ttk.Entry(row_out, textvariable=app.cutter_output_var).pack(side=tk.LEFT, fill=tk.X,
                                                               expand=True, padx=app.px(5))
    ttk.Button(row_out, text=t("labels.browse_output"),
               command=lambda: choose_output(app)).pack(side=tk.LEFT, padx=app.px(5))

    ttk.Label(parent, text=CUTTER_PATH, style="Muted.TLabel").pack(fill=tk.X, padx=app.px(5),
                                                                   pady=(app.px(2), 0))


def choose_input(app):
    from tkinter import filedialog

    path = filedialog.askopenfilename(
        title=t("labels.browse_input"),
        filetypes=[("pez / zip", "*.pez;*.zip"), (t("dialogs.filter_all"), "*.*")])
    if not path:
        path = filedialog.askdirectory(title=t("labels.browse_input"))
    if path:
        app.cutter_input_var.set(path)


def choose_output(app):
    from tkinter import filedialog

    path = filedialog.asksaveasfilename(title=t("labels.browse_output"),
                                        defaultextension=".pez",
                                        filetypes=[("pez", "*.pez")])
    if path:
        app.cutter_output_var.set(path)


def process(app, data):
    """调用外部程序做全谱切割合并。"""
    source = (app.cutter_input_var.get() or "").strip()
    target = (app.cutter_output_var.get() or "").strip()
    if not source:
        raise Exception(t("errors.input_empty"))

    if not os.path.exists(CUTTER_PATH):
        raise Exception(t("labels.cutter_missing", path=CUTTER_PATH))

    args = [CUTTER_PATH, source]
    if target:
        args.append(target)
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=1800)
    except Exception as e:
        raise Exception("%s: %s" % (os.path.basename(CUTTER_PATH), e))

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        raise Exception("%s (rc=%s)%s" % (os.path.basename(CUTTER_PATH), completed.returncode,
                                          (": " + detail[-1]) if detail else ""))

    # 输出：外部程序没给目标路径时，默认写在与输入同名的 .pez
    if not target:
        target = os.path.splitext(source)[0] + ".pez"
    return {"pez": target, "exists": os.path.exists(target)}
