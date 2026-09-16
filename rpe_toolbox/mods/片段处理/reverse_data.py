# -*- coding: utf-8 -*-
"""模组：倒序/拉伸

所属功能组：片段处理
MOD_KEY 与 assets/lang/*.json 里 functions[].key 对应；序号由主程序加载时决定，本文件不写序号。
"""

import copy

from rpe_toolbox.i18n import t

import tkinter as tk
from tkinter import ttk
from rpe_toolbox.i18n import t

MOD_KEY = "reverse_data"
MOD_ORDER = 70

def process(app, data):
    # 倒序/拉伸：t'[i] = t[0] + (t[i] - t[0]) * r
    # 保持第一个事件的开始时间与输入一致，不反转顺序
    try:
        ratio = float(app.stretch_ratio_var.get())
    except ValueError:
        raise Exception(t("errors.stretch_ratio_number"))

    if ratio == 0:
        raise Exception(t("errors.stretch_ratio_zero"))

    negative = ratio < 0

    if "notes" in data and data.get("notes"):
        notes = copy.deepcopy(data["notes"])
        # 找到第一个（最早）开始时间
        first_start = min(app.time_to_float(n["startTime"]) for n in notes)
        stretched_notes = []
        for note in notes:
            new_note = copy.deepcopy(note)
            for key in ("startTime", "endTime"):
                if key in new_note:
                    value = app.time_to_float(new_note[key])
                    new_note[key] = app.float_to_time(first_start + (value - first_start) * ratio)
            if negative:
                if "yOffset" in new_note and isinstance(new_note.get("yOffset"), (int, float)):
                    new_note["yOffset"] = -float(new_note["yOffset"])
                # 倒序时保证 hold 等音符的 startTime 早于 endTime
                start_val = app.time_to_float(new_note.get("startTime", [0, 0, 1]))
                end_val = app.time_to_float(new_note.get("endTime", new_note.get("startTime", [0, 0, 1])))
                if end_val < start_val:
                    new_note["startTime"], new_note["endTime"] = new_note["endTime"], new_note["startTime"]
            stretched_notes.append(new_note)
        data["notes"] = stretched_notes
        return data

    if "events" in data and data.get("events"):
        events = copy.deepcopy(data["events"])
        first_start = min(app.time_to_float(e["startTime"]) for e in events)
        stretched_events = []
        for event in events:
            new_event = copy.deepcopy(event)
            for key in ("startTime", "endTime"):
                if key in new_event:
                    value = app.time_to_float(new_event[key])
                    new_event[key] = app.float_to_time(first_start + (value - first_start) * ratio)
            if negative:
                _reverse_event_fields(app, new_event)
            stretched_events.append(new_event)
        data["events"] = stretched_events
        return data

    return data


def _reverse_event_fields(app, event):
    """倒序拉伸适配：保证事件开始时间早于结束时间，
    并交换 start/end 值、in/out 缓动、缓动起始/结束值（先交换再被 1 减）、贝塞尔属性。"""
    start_val = app.time_to_float(event.get("startTime", [0, 0, 1]))
    end_val = app.time_to_float(event.get("endTime", event.get("startTime", [0, 0, 1])))
    if start_val <= end_val:
        return
    # 交换开始/结束时间
    event["startTime"], event["endTime"] = event["endTime"], event["startTime"]
    # 交换开始/结束值
    if "start" in event and "end" in event:
        event["start"], event["end"] = event["end"], event["start"]
    # in 与 out 缓动交换
    easing_type = event.get("easingType", 1)
    event["easingType"] = {2: 3, 3: 2, 4: 5, 5: 4, 8: 9, 9: 8, 10: 11, 11: 10,
                           14: 15, 15: 14, 16: 17, 17: 16, 18: 19, 19: 18,
                           20: 21, 21: 20, 24: 25, 25: 24, 26: 27, 27: 26}.get(easing_type, easing_type)
    # 缓动起始/结束值先交换再被 1 减
    if "easingLeft" in event and "easingRight" in event:
        left = event.get("easingLeft", 0.0)
        right = event.get("easingRight", 1.0)
        event["easingLeft"] = 1.0 - right
        event["easingRight"] = 1.0 - left
    # 贝塞尔属性适配
    if event.get("bezier") == 1 and isinstance(event.get("bezierPoints"), list) and len(event["bezierPoints"]) == 4:
        x1, y1, x2, y2 = event["bezierPoints"]
        event["bezierPoints"] = [1.0 - x2, 1.0 - y2, 1.0 - x1, 1.0 - y1]


def build_options(app, parent):
    """在标签页里创建本功能的选项控件（由主程序在加载模组时调用）。"""
    # 功能 7：倒序/拉伸
    app.frame_stretch_settings = ttk.Frame(app.tab_frames["reverse_data"])
    app.frame_stretch_settings.pack(fill=tk.X, pady=app.px(2))
    ttk.Label(app.frame_stretch_settings, text=t("labels.stretch_ratio")).pack(side=tk.LEFT, padx=app.px(5))
    ttk.Entry(app.frame_stretch_settings, textvariable=app.stretch_ratio_var, width=8).pack(side=tk.LEFT, padx=app.px(5))
    ttk.Label(app.frame_stretch_settings, text=t("labels.stretch_ratio_hint"), style="Muted.TLabel").pack(side=tk.LEFT, padx=app.px(5))
