# -*- coding: utf-8 -*-
"""模组：时间间隔转 y 偏移

所属功能组：片段处理
MOD_KEY 与 assets/lang/*.json 里 functions[].key 对应；序号由主程序加载时决定，本文件不写序号。
"""

import copy

from rpe_toolbox.i18n import t

import tkinter as tk
from tkinter import ttk
from rpe_toolbox.i18n import t

MOD_KEY = "time_interval_to_yoffset"
MOD_ORDER = 60

def process(app, data):
    notes = data.get("notes", [])
    if not notes:
        return data

    try:
        flow_speed = float(app.time_offset_speed_var.get())
        bpm = float(app.time_offset_bpm_var.get())
    except ValueError:
        raise Exception(t("errors.speed_bpm_number"))
    if bpm <= 0:
        raise Exception(t("errors.bpm_positive"))

    unify_start_time = app.time_offset_unify_var.get()
    first_start = app.time_to_float(notes[0].get("startTime", [0, 0, 1]))
    converted = []

    for idx, note in enumerate(notes):
        new_note = copy.deepcopy(note)
        original_start = app.time_to_float(new_note.get("startTime", [0, 0, 1]))
        if unify_start_time:
            new_note["startTime"] = app.float_to_time(first_start)
        else:
            new_note["startTime"] = new_note.get("startTime", [0, 0, 1])

        if idx == 0:
            new_note["yOffset"] = 0.0
        else:
            delta_beats = original_start - first_start
            delta_seconds = delta_beats * 60.0 / bpm
            y_offset = delta_seconds * flow_speed * 120.0
            new_note["yOffset"] = round(y_offset, 4)

        converted.append(new_note)

    data["notes"] = converted
    return data


def build_options(app, parent):
    """在标签页里创建本功能的选项控件（由主程序在加载模组时调用）。"""
    # 功能 6：时间间隔转 y 偏移
    app.frame_time_offset_settings = ttk.Frame(app.tab_frames["time_interval_to_yoffset"])
    app.frame_time_offset_settings.pack(fill=tk.X, pady=app.px(2))
    ttk.Label(app.frame_time_offset_settings, text=t("labels.speed")).pack(side=tk.LEFT, padx=app.px(5))
    ttk.Entry(app.frame_time_offset_settings, textvariable=app.time_offset_speed_var, width=8).pack(side=tk.LEFT, padx=app.px(5))
    ttk.Label(app.frame_time_offset_settings, text=t("labels.bpm")).pack(side=tk.LEFT, padx=app.px(5))
    ttk.Entry(app.frame_time_offset_settings, textvariable=app.time_offset_bpm_var, width=8).pack(side=tk.LEFT, padx=app.px(5))
    app.time_offset_unify_check = ttk.Checkbutton(app.frame_time_offset_settings, text=t("labels.unify_start_time"), variable=app.time_offset_unify_var)
    app.time_offset_unify_check.pack(side=tk.LEFT, padx=app.px(5))
