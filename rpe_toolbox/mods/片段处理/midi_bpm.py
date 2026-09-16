# -*- coding: utf-8 -*-
"""模组：MIDI BPM 提取

所属功能组：片段处理
MOD_KEY 与 assets/lang/*.json 里 functions[].key 对应；序号由主程序加载时决定，本文件不写序号。
"""

import os

from rpe_toolbox.i18n import t

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from rpe_toolbox.i18n import t

MOD_KEY = "midi_bpm_extract"
MOD_ORDER = 80

def process(app, data):
    midi_path = app.midi_path_var.get().strip()
    if not midi_path or not os.path.exists(midi_path):
        raise Exception(t("errors.midi_invalid"))

    with open(midi_path, "rb") as fh:
        raw = fh.read()

    if raw[:4] != b"MThd":
        raise Exception(t("errors.midi_not_standard"))

    if len(raw) < 14:
        raise Exception(t("errors.midi_too_short"))

    division = int.from_bytes(raw[12:14], byteorder="big", signed=True)
    if division == 0:
        raise Exception(t("errors.midi_resolution_invalid"))

    offset = 14
    bpm_changes = []
    current_beat = 0.0
    running_status = None

    while offset < len(raw):
        if raw[offset:offset + 4] != b"MTrk":
            break
        track_len = int.from_bytes(raw[offset + 4:offset + 8], byteorder="big")
        track_data = raw[offset + 8:offset + 8 + track_len]
        offset += 8 + track_len

        cursor = 0
        delta = 0
        while cursor < len(track_data):
            delta, cursor = _read_var_int(app, track_data, cursor)
            current_beat += delta / max(division, 1)

            if cursor >= len(track_data):
                break

            status = track_data[cursor]
            if status < 0x80:
                if running_status is None:
                    raise Exception(t("errors.midi_running_status_missing"))
                event_status = running_status
                event_data = status
            else:
                running_status = status
                event_status = status
                cursor += 1
                if cursor >= len(track_data):
                    break
                event_data = track_data[cursor]
                cursor += 1

            if event_status == 0xFF:
                meta_type = event_data
                if cursor >= len(track_data):
                    break
                meta_len, cursor = _read_var_int(app, track_data, cursor)
                meta_bytes = track_data[cursor:cursor + meta_len]
                cursor += meta_len
                if meta_type == 0x51 and len(meta_bytes) >= 3:
                    tempo = int.from_bytes(meta_bytes[:3], byteorder="big")
                    bpm = 60000000.0 / tempo
                    bpm_changes.append({
                        "bpm": round(bpm, 3),
                        "startTime": app.float_to_time(current_beat),
                    })
            elif event_status == 0xF0 or event_status == 0xF7:
                if cursor >= len(track_data):
                    break
                length, cursor = _read_var_int(app, track_data, cursor)
                cursor += length
            elif event_status < 0xF0:
                # 普通通道消息（0x80~0xEF）：仅跳过数据字节（C0/D0 一个，其余两个）
                cursor += 1
                if event_status not in (0xC0, 0xD0):
                    cursor += 1

    if not bpm_changes:
        raise Exception(t("errors.midi_no_bpm"))

    # 需求九：输出格式为 BPMList（bpm + startTime），无需 midiPath
    return {"BPMList": bpm_changes}


def _read_var_int(app, data, offset):
    value = 0
    while True:
        if offset >= len(data):
            raise Exception(t("errors.midi_incomplete"))
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if byte < 0x80:
            break
    return value, offset


def build_options(app, parent):
    """在标签页里创建本功能的选项控件（由主程序在加载模组时调用）。"""
    # 功能 8：MIDI BPM 提取
    app.frame_midi_settings = ttk.Frame(app.tab_frames["midi_bpm_extract"])
    app.frame_midi_settings.pack(fill=tk.X, pady=app.px(2))
    ttk.Label(app.frame_midi_settings, text=t("labels.midi_path")).pack(side=tk.LEFT, padx=app.px(5))
    app.entry_midi_path = ttk.Entry(app.frame_midi_settings, textvariable=app.midi_path_var, width=55)
    app.entry_midi_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=app.px(5))
    # 回调指向本模组的模块级函数：select_midi_file 只是本文件里的函数，app 上没有同名方法
    app.btn_select_midi = ttk.Button(app.frame_midi_settings, text=t("buttons.browse_midi"),
                                     command=lambda: select_midi_file(app))
    app.btn_select_midi.pack(side=tk.LEFT, padx=app.px(5))


def select_midi_file(app):
    path = filedialog.askopenfilename(
        title=t("dialogs.choose_midi_title"),
        filetypes=[(t("dialogs.filter_midi"), "*.mid;*.midi"), (t("dialogs.filter_all"), "*.*")]
    )
    if path:
        app.midi_path_var.set(path)
