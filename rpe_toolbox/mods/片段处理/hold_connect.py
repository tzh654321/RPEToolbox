# -*- coding: utf-8 -*-
"""模组：hold/事件首尾相接

所属功能组：片段处理
MOD_KEY 与 assets/lang/*.json 里 functions[].key 对应；序号由主程序加载时决定，本文件不写序号。
"""

import copy

from rpe_toolbox.i18n import t

import tkinter as tk
from tkinter import ttk
from rpe_toolbox.i18n import t

MOD_KEY = "hold_notes_connect"
MOD_ORDER = 10

def process(app, data):
    distinguish = app.distinguish_track_var.get()
    allow_shorten = app.allow_shorten_var.get()

    if "notes" in data and data.get("notes"):
        notes = copy.deepcopy(data["notes"])
        if distinguish:
            # 区分轨道：按 x 坐标差距 < 175 分组，组内仅对 x 差距 < 175 的前后相邻 hold 首尾相接
            groups = _group_notes_by_track(app, notes)
            for group in groups:
                _connect_group_notes(app, group, allow_shorten)
        else:
            # 不区分轨道：按唯一开始时间连接
            unique_start_times = sorted(set(app.time_to_float(n["startTime"]) for n in notes))
            for note in notes:
                if note.get("type") != 2:
                    continue
                current_start = app.time_to_float(note["startTime"])
                current_end = app.time_to_float(note.get("endTime", note["startTime"]))
                next_start_time_val = _next_unique_time(app, unique_start_times, current_start)
                if next_start_time_val is None:
                    continue
                if allow_shorten or next_start_time_val > current_end + 1e-9:
                    note["endTime"] = app.float_to_time(next_start_time_val)
                elif next_start_time_val < current_end - 1e-9:
                    # 不允许缩短：本会被缩短的长条改为从其结束时间起
                    # 寻找下一个音符开始时间来延长；找不到则保持原样
                    extend_time = _next_unique_time(app, unique_start_times, current_end)
                    if extend_time is not None:
                        note["endTime"] = app.float_to_time(extend_time)
                # next_start ≈ current_end：已首尾相接，保持不变
        data["notes"] = notes
        return data

    if "events" in data and data.get("events"):
        events = copy.deepcopy(data["events"])
        if distinguish:
            # 区分轨道：按 line 字段分组，组内首尾相接
            groups = {}
            for ev in events:
                groups.setdefault(ev.get("line", 0), []).append(ev)
            for group in groups.values():
                _connect_group_events(app, group, allow_shorten)
        else:
            # 不区分轨道：按唯一开始时间连接
            unique_start_times = sorted(set(app.time_to_float(e["startTime"]) for e in events))
            for ev in events:
                current_start = app.time_to_float(ev["startTime"])
                current_end = app.time_to_float(ev.get("endTime", ev["startTime"]))
                next_start_time_val = _next_unique_time(app, unique_start_times, current_start)
                if next_start_time_val is None:
                    continue
                if allow_shorten or next_start_time_val > current_end + 1e-9:
                    ev["endTime"] = app.float_to_time(next_start_time_val)
                elif next_start_time_val < current_end - 1e-9:
                    # 不允许缩短：本会被缩短的事件改为从其结束时间起延长
                    extend_time = _next_unique_time(app, unique_start_times, current_end)
                    if extend_time is not None:
                        ev["endTime"] = app.float_to_time(extend_time)
                # next_start ≈ current_end：已首尾相接，保持不变
        data["events"] = events
        return data

    return data


def _next_unique_time(app, sorted_times, after_t):
    """返回 sorted_times 中第一个严格晚于 after_t（留 1e-9 容差）的时间，没有则 None"""
    for t in sorted_times:
        if t > after_t + 1e-9:
            return t
    return None


def _group_notes_by_track(app, notes):
    """将 hold 音符按 x 坐标差距 < 175 分组（相邻差距 < 175 视为同一轨道）"""
    hold_notes = [n for n in notes if n.get("type") == 2]
    if not hold_notes:
        return []
    # 按 x 坐标排序
    hold_notes.sort(key=lambda n: n.get("positionX", 0.0))
    groups = []
    current_group = [hold_notes[0]]
    for note in hold_notes[1:]:
        prev_x = current_group[-1].get("positionX", 0.0)
        cur_x = note.get("positionX", 0.0)
        if abs(cur_x - prev_x) < 175:
            current_group.append(note)
        else:
            groups.append(current_group)
            current_group = [note]
    groups.append(current_group)
    return groups


def _connect_group_notes(app, group, allow_shorten=True):
    """组内 hold 按时间排序，仅当下一根 hold 的 x 坐标差距 < 175 时首尾相接；
    相同开始时间的 hold（双押）共同参考下一个不同开始时间。
    不允许缩短时，本会被缩短的 hold 改为从其结束时间起寻找下一个满足轨道条件的开始时间。"""
    group.sort(key=lambda n: app.time_to_float(n["startTime"]))
    unique_times = sorted(set(app.time_to_float(n["startTime"]) for n in group))
    for note in group:
        cur_t = app.time_to_float(note["startTime"])
        cur_x = note.get("positionX", 0.0)
        cur_end = app.time_to_float(note.get("endTime", note["startTime"]))
        next_time = _next_unique_time(app, unique_times, cur_t)
        if next_time is None:
            continue
        candidates = [n for n in group
                      if abs(app.time_to_float(n["startTime"]) - next_time) < 1e-9
                      and abs(n.get("positionX", 0.0) - cur_x) < 175]
        if not candidates:
            continue
        if allow_shorten or next_time > cur_end + 1e-9:
            note["endTime"] = copy.deepcopy(candidates[0]["startTime"])
        elif next_time < cur_end - 1e-9:
            # 不允许缩短：从结束时间起寻找下一个满足轨道条件的开始时间来延长
            extend_time = _next_unique_time(app, unique_times, cur_end)
            if extend_time is not None:
                ext_candidates = [n for n in group
                                  if abs(app.time_to_float(n["startTime"]) - extend_time) < 1e-9
                                  and abs(n.get("positionX", 0.0) - cur_x) < 175]
                if ext_candidates:
                    note["endTime"] = copy.deepcopy(ext_candidates[0]["startTime"])


def _connect_group_events(app, group, allow_shorten=True):
    """组内事件按时间排序，首尾相接（endTime = 下一个不同 startTime）。
    不允许缩短时，本会被缩短的事件改为从其结束时间起寻找下一个开始时间。"""
    group.sort(key=lambda e: app.time_to_float(e["startTime"]))
    unique_times = sorted(set(app.time_to_float(e["startTime"]) for e in group))
    for ev in group:
        cur_t = app.time_to_float(ev["startTime"])
        cur_end = app.time_to_float(ev.get("endTime", ev["startTime"]))
        next_time = _next_unique_time(app, unique_times, cur_t)
        if next_time is None:
            continue
        if allow_shorten or next_time > cur_end + 1e-9:
            ev["endTime"] = copy.deepcopy(app.float_to_time(next_time))
        elif next_time < cur_end - 1e-9:
            # 不允许缩短：从结束时间起寻找下一个开始时间来延长
            extend_time = _next_unique_time(app, unique_times, cur_end)
            if extend_time is not None:
                ev["endTime"] = copy.deepcopy(app.float_to_time(extend_time))


def build_options(app, parent):
    """在标签页里创建本功能的选项控件（由主程序在加载模组时调用）。"""
    # 功能 1：hold/事件首尾相接
    app.frame_hold_options = ttk.Frame(app.tab_frames["hold_notes_connect"])
    app.frame_hold_options.pack(fill=tk.X, pady=app.px(2))
    app.allow_shorten_check = ttk.Checkbutton(app.frame_hold_options, text=t("labels.allow_shorten"), variable=app.allow_shorten_var)
    app.allow_shorten_check.pack(side=tk.LEFT, padx=app.px(5))
    app.distinguish_track_check = ttk.Checkbutton(app.frame_hold_options, text=t("labels.distinguish_track"), variable=app.distinguish_track_var)
    app.distinguish_track_check.pack(side=tk.LEFT, padx=app.px(5))
