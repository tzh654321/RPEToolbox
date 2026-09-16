# -*- coding: utf-8 -*-
"""模组：事件类型转换

所属功能组：片段处理
MOD_KEY 与 assets/lang/*.json 里 functions[].key 对应；序号由主程序加载时决定，本文件不写序号。
"""

import copy

from rpe_toolbox import i18n
from rpe_toolbox.i18n import t

import tkinter as tk
from tkinter import ttk
from rpe_toolbox import i18n
from rpe_toolbox.i18n import t

MOD_KEY = "event_type_convert"
MOD_ORDER = 40

def process(app, data):
    events = data.get("events", [])
    if not events:
        return data

    # 1. 常规行（输入选择框 → 文字）：按行把源类型转换为目标类型
    converted = []
    for event in events:
        new_event = copy.deepcopy(event)
        original_type = new_event.get("type")
        for idx in range(len(app.event_source_vars)):
            source_label = app.event_source_vars[idx].get()
            target_label = app.event_target_vars[idx].get()
            if source_label == target_label:
                continue
            source_type = app._get_event_type_number(source_label)
            target_type = app._get_event_type_number(target_label)
            if source_type is not None and target_type is not None and original_type == source_type:
                new_event["type"] = target_type
                break
        converted.append(new_event)

    # 2. 定轨hold：把事件当作五/七列 hold
    notes = []
    hold_mode = i18n.option_key("hold_mode", app.hold_mode_var.get())
    if hold_mode in ("5k", "7k"):
        k = 5 if hold_mode == "5k" else 7
        notes.extend(_events_to_hold_notes(app, converted, k))

    # 3. 曲线drag：把位移与缩放按音符间隔转换成一系列 drag
    drag_mode = i18n.option_key("drag_mode", app.drag_mode_var.get())
    if drag_mode != "none":
        try:
            density = int(app.drag_interval_var.get())
        except ValueError:
            raise Exception(t("errors.drag_interval_int"))
        if density <= 0:
            raise Exception(t("errors.drag_interval_positive"))
        axis = "x" if drag_mode == "x" else "y"
        notes.extend(_events_to_drag_notes(app, converted, axis, density))

    if notes:
        # 相同时间+位置的音符去重（后生成的覆盖先生成的，边界处取后一段事件）
        seen = {}
        for n in notes:
            seen[(tuple(n["startTime"]), n["positionX"])] = n
        result_notes = sorted(
            seen.values(),
            key=lambda n: (app.time_to_float(n["startTime"]), n["positionX"]),
        )
        return {"notes": result_notes}

    data["events"] = converted
    return data


def _make_base_note(app, type, positionX, startTime, endTime=None, size=1.0, judgeArea=None):
    """生成统一格式的 note（与图片转音符画输出格式一致）。"""
    return {
        "above": 1,
        "alpha": 255,
        "endTime": copy.deepcopy(endTime) if endTime is not None else copy.deepcopy(startTime),
        "isFake": 0,
        "judgeArea": judgeArea if judgeArea is not None else size,
        "line": 0,
        "positionX": positionX,
        "size": size,
        "speed": 1.0,
        "startTime": copy.deepcopy(startTime),
        "tint": [255, 255, 255],
        "type": type,
        "visibleTime": 999999.0,
        "yOffset": 0.0,
    }


def _events_to_hold_notes(app, events, k):
    """定轨hold：事件类型 1..k 分别映射到 k 列固定轨道，生成 hold 音符。
    5k 列位：-540/-270/0/270/540；7k 列位：-578.57/-385.71/-192.86/0/192.86/385.71/578.57。"""
    positions = [round((i - (k - 1) / 2.0) * 1350.0 / k, 2) for i in range(k)]
    notes = []
    for ev in events:
        t = ev.get("type")
        if not isinstance(t, int) or not (1 <= t <= k):
            continue
        start_time = ev.get("startTime", [0, 0, 1])
        end_time = ev.get("endTime", start_time)
        notes.append(_make_base_note(app, 
            type=2,
            positionX=positions[t - 1],
            startTime=start_time,
            endTime=end_time,
        ))
    return notes


def _events_to_drag_notes(app, events, axis, density):
    """曲线drag：把位移事件（x→type1 / y→type2）与缩放事件（x→type6 / y→type7）
    按音符间隔采样成一系列 drag 音符；无缩放事件覆盖时 size/judgeArea 取 1.0。"""
    move_type = 1 if axis == "x" else 2
    scale_type = 6 if axis == "x" else 7
    step = 4.0 / density
    if step <= 0:
        step = 0.25

    move_events = [e for e in events if e.get("type") == move_type]
    scale_events = [e for e in events if e.get("type") == scale_type]
    scale_events.sort(key=lambda e: app.time_to_float(e.get("startTime", [0, 0, 1])))

    def scale_at(t):
        # 覆盖 t 的活动缩放事件内插值；否则沿用上一个事件的结束值；再否则 1.0
        active = None
        for e in scale_events:
            s = app.time_to_float(e["startTime"])
            en = app.time_to_float(e.get("endTime", e["startTime"]))
            if s - 1e-9 <= t <= en + 1e-9:
                active = e
                break
        if active:
            s = app.time_to_float(active["startTime"])
            en = app.time_to_float(active.get("endTime", active["startTime"]))
            dur = en - s
            if dur < 1e-6:
                return active.get("end", 1.0)
            p = (t - s) / dur
            return app.interpolate_value(
                active.get("start", 1.0),
                active.get("end", 1.0),
                p,
                active.get("easingType", 1),
                active.get("bezier", 0),
                active.get("bezierPoints", [0.0, 0.0, 0.0, 0.0]),
            )
        prev = None
        for e in scale_events:
            en = app.time_to_float(e.get("endTime", e["startTime"]))
            if en < t - 1e-9:
                prev = e.get("end", 1.0)
            else:
                break
        return prev if prev is not None else 1.0

    notes = []
    for ev in move_events:
        t0 = app.time_to_float(ev.get("startTime", [0, 0, 1]))
        t1 = app.time_to_float(ev.get("endTime", ev.get("startTime", [0, 0, 1])))
        start_val = ev.get("start", 0.0)
        end_val = ev.get("end", start_val)

        if t1 <= t0 + 1e-9:
            size = round(max(0.05, scale_at(t0)), 4)
            notes.append(_make_base_note(app, 
                type=4,
                positionX=start_val,
                startTime=app.float_to_time(t0),
                size=size,
            ))
            continue

        t = t0
        while t <= t1 + 1e-6:
            p = (t - t0) / (t1 - t0)
            val = app.interpolate_value(
                start_val, end_val, p,
                ev.get("easingType", 1),
                ev.get("bezier", 0),
                ev.get("bezierPoints", [0.0, 0.0, 0.0, 0.0]),
            )
            size = round(max(0.05, scale_at(t)), 4)
            notes.append(_make_base_note(app, 
                type=4,
                positionX=val,
                startTime=app.float_to_time(t),
                size=size,
            ))
            t += step
    return notes


def build_options(app, parent):
    """在标签页里创建本功能的选项控件（由主程序在加载模组时调用）。"""
    # 功能 4：事件类型转换（两列“输入选择框 → 文字”）
    app.frame_event_convert = ttk.Frame(app.tab_frames["event_type_convert"])
    app.frame_event_convert.pack(fill=tk.X, pady=app.px(2))
    _create_event_convert_rows(app, )


def _create_event_convert_rows(app):
    # 需求十一：两列布局，每行“输入选择框 → 文字”，速度更名为流速
    app.frame_event_convert_left = ttk.Frame(app.frame_event_convert)
    app.frame_event_convert_left.pack(side=tk.LEFT, fill=tk.X, padx=(app.px(5), app.px(25)), pady=app.px(2))
    app.frame_event_convert_right = ttk.Frame(app.frame_event_convert)
    app.frame_event_convert_right.pack(side=tk.LEFT, fill=tk.X, padx=(app.px(0), app.px(5)), pady=app.px(2))

    app.event_source_vars = []
    app.event_target_vars = []

    type_names = [name for name, _ in app.event_type_options]
    # 左列：X轴位移 Y轴位移 旋转 透明度 流速；右列：X轴缩放 Y轴缩放 定轨hold 曲线drag 音符间隔
    standard_keys = ["1", "2", "3", "4", "5", "6", "7"]
    for idx, type_key in enumerate(standard_keys):
        name = i18n.option_display("event_type", type_key)
        parent = app.frame_event_convert_left if idx < 5 else app.frame_event_convert_right
        row = idx if idx < 5 else idx - 5
        source_var = tk.StringVar(value=name)
        target_var = tk.StringVar(value=name)
        app.event_source_vars.append(source_var)
        app.event_target_vars.append(target_var)
        ttk.Combobox(parent, textvariable=source_var, values=type_names, state="readonly", width=14).grid(
            row=row, column=0, sticky="w", padx=app.px(2), pady=app.px(2))
        ttk.Label(parent, text=t("labels.arrow"), width=3, anchor="center").grid(
            row=row, column=1, sticky="w", padx=app.px(1), pady=app.px(2))
        ttk.Label(parent, text=name, width=11, anchor="w").grid(
            row=row, column=2, sticky="w", padx=app.px(2), pady=app.px(2))

    # 定轨hold：无/5k/7k，默认无
    app.hold_mode_var = tk.StringVar(value=i18n.option_display("hold_mode", "none"))
    ttk.Combobox(app.frame_event_convert_right, textvariable=app.hold_mode_var,
                 values=i18n.option_values("hold_mode"), state="readonly", width=14).grid(
        row=2, column=0, sticky="w", padx=app.px(2), pady=app.px(2))
    ttk.Label(app.frame_event_convert_right, text=t("labels.arrow"), width=3, anchor="center").grid(
        row=2, column=1, sticky="w", padx=app.px(1), pady=app.px(2))
    ttk.Label(app.frame_event_convert_right, text=t("labels.hold_track"), width=11, anchor="w").grid(
        row=2, column=2, sticky="w", padx=app.px(2), pady=app.px(2))

    # 曲线drag：无/X轴位移与缩放/y轴位移与缩放，默认无
    app.drag_mode_var = tk.StringVar(value=i18n.option_display("drag_mode", "none"))
    ttk.Combobox(app.frame_event_convert_right, textvariable=app.drag_mode_var,
                 values=i18n.option_values("drag_mode"), state="readonly", width=14).grid(
        row=3, column=0, sticky="w", padx=app.px(2), pady=app.px(2))
    ttk.Label(app.frame_event_convert_right, text=t("labels.arrow"), width=3, anchor="center").grid(
        row=3, column=1, sticky="w", padx=app.px(1), pady=app.px(2))
    ttk.Label(app.frame_event_convert_right, text=t("labels.drag_curve"), width=11, anchor="w").grid(
        row=3, column=2, sticky="w", padx=app.px(2), pady=app.px(2))

    # 音符间隔（输入框，仅曲线drag不为“无”时出现）
    app.frame_drag_interval = ttk.Frame(app.frame_event_convert_right)
    app.frame_drag_interval.grid(row=4, column=0, columnspan=3, sticky="w", padx=app.px(2), pady=app.px(2))
    app.drag_interval_var = tk.StringVar(value="16")
    ttk.Entry(app.frame_drag_interval, textvariable=app.drag_interval_var, width=8).pack(side=tk.LEFT, padx=app.px(2))
    ttk.Label(app.frame_drag_interval, text=t("labels.arrow"), width=3, anchor="center").pack(side=tk.LEFT, padx=app.px(1))
    ttk.Label(app.frame_drag_interval, text=t("labels.drag_interval"), width=11, anchor="w").pack(side=tk.LEFT, padx=app.px(2))
    app.frame_drag_interval.grid_remove()
    app.drag_mode_var.trace_add("write", lambda *_: _toggle_drag_interval(app, ))


def _toggle_drag_interval(app):
    if i18n.option_key("drag_mode", app.drag_mode_var.get()) != "none":
        app.frame_drag_interval.grid()
    else:
        app.frame_drag_interval.grid_remove()
