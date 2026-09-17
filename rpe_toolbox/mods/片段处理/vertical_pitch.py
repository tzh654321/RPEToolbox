# -*- coding: utf-8 -*-
"""模组：纵连音高

所属功能组：片段处理
MOD_KEY 与 assets/lang/*.json 里 functions[].key 对应；序号由主程序加载时决定，本文件不写序号。

用途
----
高频率重复播放同一个音效时，人耳听到的是「重复频率」对应的音高。把单个键**拆成一串纵连**
（同一 x 坐标、沿时间轴依次排列的一串音符），谱面播放时这一串就会以该频率连续触发，
于是能听到指定的音高；给不同的键指定不同音高，就能用纵连「弹出旋律」。

数量规则（hold 由 bpm 与音高自动推算，其余手填）
------------------------------------------------
    单音符时值 unit = 1 / 音高频率(Hz)          # 想听到该音高，就必须以这个间隔重复
    音高为 0（单键）时没有频率，退回一个 16 分音： unit = 60 / bpm / 4

    hold ：数量 = round(该 hold 的时长(秒) / unit)
           然后把这个 hold 沿时长等分成「数量」个音符（**首尾相接**，第 1 个的 endTime = 第 2 个的 startTime）
    hold + 滑音（音高 A→B）：重复频率随时间线性变化，
           总数 = round(时长(秒) × (fA+fB)/2)，第 k 个音符的时间由
           ∫₀ᵗ f(τ)dτ = k（f 线性）反解 → 纵连的疏密随音高变化，播出来就是滑音
    tap/drag/flick ：数量手填；第 1 个音符保持原位，其后每隔 unit 补一个

预览（锯齿波）
--------------
**下方 = 较早时间，上方 = 较晚时间**；横向 = x 坐标（±675，音符宽度 175）；时间单位为**拍**。
只对时间轴缩放/滚动，上下各留一拍空位。音高·数量标在音符**上方**。
左键点音符 → 就在画布上原地编辑（不弹窗）；右键 hold → 切换滑音。
"""

import math
import os
import re
import sys
import time
import tkinter as tk
from tkinter import ttk

from rpe_toolbox import audio, theme
from rpe_toolbox.i18n import t

MOD_KEY = "vertical_pitch"
MOD_ORDER = 90

# RPE 音符类型 → 颜色（tap/drag/flick/hold 的主要颜色）
TYPE_COLORS = {1: "#0AC3FF", 2: "#9AE8FD", 3: "#FE4365", 4: "#F0ED69"}
TYPE_NAMES = {1: "tap", 2: "hold", 3: "flick", 4: "drag"}
NAME_TYPES = {"tap": 1, "hold": 2, "flick": 3, "drag": 4}

# 预览画布：x 显示范围与音符宽度（RPE 坐标单位）
COORD_HALF = 675.0
NOTE_WIDTH = 175.0
# 时间轴上下各预留的拍数（防止音符上的文字被裁掉）
TIME_PAD_BEATS = 1.0

PITCH_RE = r"^([A-Ga-g])([#b]?)(-?\d)$"
_PITCH_NAMES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


# ----------------------------------------------------------------------
# 音高
# ----------------------------------------------------------------------
def note_pitch(state):
    return (state or {}).get("pitch") or "0"


def parse_pitch(text):
    """校验音高写法：0 / 空 表示单键；否则 音名+可选升降号+八度（C4、A#0、Gb7）。"""
    text = (text or "").strip()
    if text == "" or text == "0":
        return "0"
    m = re.match(PITCH_RE, text)
    if not m:
        return None
    return m.group(1).upper() + m.group(2) + m.group(3)


def pitch_frequency(pitch):
    """音高 → 频率（Hz）。'0'（单键）或无法解析时返回 None。"""
    if not pitch or pitch == "0":
        return None
    m = re.match(PITCH_RE, pitch)
    if not m:
        return None
    semi = _PITCH_NAMES[m.group(1).upper()]
    if m.group(2) == "#":
        semi += 1
    elif m.group(2) == "b":
        semi -= 1
    midi = 12 * (int(m.group(3)) + 1) + semi
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def parse_edit(text):
    """解析用户在画布上输入的内容。

    支持：`0`（单键）/ `C4`（音高）/ `C4→E4`（滑音，两端音高）/ `8`（非 hold 的数量）。
    返回 (pitch, pitch2, count)；无法识别的位置为 None。
    """
    text = (text or "").strip().replace("->", "\u2192").replace("—>", "\u2192")
    if not text:
        return None, None, None
    if "\u2192" in text:
        left, _, right = text.partition("\u2192")
        return parse_pitch(left), parse_pitch(right), None
    parsed = parse_pitch(text)
    if parsed is not None and not re.match(r"^-?\d+$", text):
        return parsed, None, None
    if text == "0":
        return "0", None, None
    try:
        return None, None, max(1, int(text))
    except ValueError:
        return None, None, None


# ----------------------------------------------------------------------
# 状态与换算
# ----------------------------------------------------------------------
def _bpm(app):
    try:
        return max(1e-6, float(app.vp_bpm_var.get()))
    except (AttributeError, TypeError, ValueError):
        return 120.0


def _span_beats(app, note):
    t0 = app.time_to_float(note.get("startTime", [0, 0, 1]))
    t1 = app.time_to_float(note.get("endTime", note.get("startTime", [0, 0, 1])))
    return max(0.0, t1 - t0)


def _seconds(app, note):
    return _span_beats(app, note) * 60.0 / _bpm(app)


def unit_seconds(app, pitch):
    """单音符时值（秒）：能听到该音高所需的重复间隔；单键退回一个 16 分音。"""
    freq = pitch_frequency(pitch)
    if freq:
        return 1.0 / freq
    return 60.0 / _bpm(app) / 4.0


def unit_beats(app, pitch):
    return unit_seconds(app, pitch) * _bpm(app) / 60.0


def hold_count(app, note, pitch, pitch2=None):
    """hold 的数量：由 bpm 与音高推算。

    非滑音：时长 / 单音符时值；滑音：时长 × 两端频率的平均值（重复频率线性变化时的总数）。
    """
    span = _seconds(app, note)
    f1 = pitch_frequency(pitch)
    f2 = pitch_frequency(pitch2) if pitch2 else None
    if f1 and f2 and abs(f2 - f1) > 1e-9:
        return max(1, int(round(span * (f1 + f2) / 2.0)))
    unit = unit_seconds(app, pitch)
    if unit <= 0:
        return 1
    return max(1, int(round(span / unit)))


def effective_count(app, note, state):
    """hold 用推算值；其余用用户手填的数量。

    只有**开启滑音**时才把尾端音高算进频率平均里 —— 否则把滑音关掉之后，
    数量仍然是按两端平均值算的，与「非滑音」不符。
    """
    if int(note.get("type", 1)) == 2:
        pitch2 = state.get("pitch2") if state.get("glide") else None
        return hold_count(app, note, note_pitch(state), pitch2)
    try:
        return max(1, int(state.get("count", 1)))
    except (TypeError, ValueError):
        return 1


def _state_list(app, notes):
    """输入音符与编辑状态对齐（长度变化时保留能对上的部分）。"""
    old = getattr(app, "vp_states", []) or []
    states = []
    for index in range(len(notes)):
        if index < len(old):
            states.append(old[index])
        else:
            states.append({"pitch": "0", "count": 1, "glide": False, "pitch2": "0"})
    app.vp_states = states
    return states


# ----------------------------------------------------------------------
# 界面
# ----------------------------------------------------------------------
def build_options(app, parent):
    """bpm / 填充音符 / 预览 + 可视化编辑区。"""
    app.vp_states = []
    app.vp_selected = None
    app.vp_notes = []
    app.vp_zoom = 1.0
    app.vp_scroll = 0.0
    app.vp_editor = None
    app.vp_editor_item = None
    app.vp_editor_index = None
    app.vp_editor_kind = "main"

    row = ttk.Frame(parent)
    row.pack(fill=tk.X, pady=app.px(2))
    ttk.Label(row, text=t("labels.bpm")).pack(side=tk.LEFT, padx=app.px(5))
    app.vp_bpm_var = tk.StringVar(value="120")
    ttk.Entry(row, textvariable=app.vp_bpm_var, width=8).pack(side=tk.LEFT, padx=app.px(5))

    ttk.Label(row, text=t("labels.fill_note")).pack(side=tk.LEFT, padx=app.px(5))
    app.vp_fill_var = tk.StringVar(value=t("labels.fill_same_as_input"))
    fill_values = [TYPE_NAMES[1], TYPE_NAMES[2], TYPE_NAMES[3], TYPE_NAMES[4],
                   t("labels.fill_same_as_input")]
    ttk.Combobox(row, textvariable=app.vp_fill_var, state="readonly", width=14,
                 values=fill_values).pack(side=tk.LEFT, padx=app.px(5))

    ttk.Button(row, text=t("buttons.preview"),
               command=lambda: preview(app)).pack(side=tk.LEFT, padx=app.px(5))
    ttk.Button(row, text=t("buttons.refresh"),
               command=lambda: refresh(app)).pack(side=tk.LEFT, padx=app.px(5))

    # 可视化区：纵向 = 时间（下早↑晚），横向 = x 坐标；高度固定，让输入/输出框能等分剩下的空间
    app.vp_canvas = tk.Canvas(parent, height=app.px(240), bd=0, highlightthickness=1)
    app.vp_canvas.pack(fill=tk.X, pady=app.px(4))

    app.vp_canvas.bind("<MouseWheel>", lambda e: scroll_canvas(app, e))
    app.vp_canvas.bind("<Control-MouseWheel>", lambda e: zoom_canvas(app, e))
    app.vp_canvas.bind("<Button-1>", lambda e: click_canvas(app, e, right=False))
    app.vp_canvas.bind("<Button-3>", lambda e: click_canvas(app, e, right=True))
    try:
        app.text_input.bind("<<Modified>>", lambda e: _on_input_modified(app), add="+")
    except Exception:
        pass

    # 点窗口里任何地方都要先把当前编辑框的内容存下来（用户不按回车也不该丢）
    if not getattr(app, "_vp_hooks_installed", False):
        app._vp_hooks_installed = True
        app.root.bind("<Button-1>", lambda e: _on_root_click(app, e), add="+")
        if hasattr(app, "register_pending_commit"):
            app.register_pending_commit(lambda: _commit_editor(app))


def _on_input_modified(app):
    try:
        widget = app.text_input
        if not widget.edit_modified():
            return
        widget.edit_modified(False)
        refresh(app)
    except Exception:
        pass


def refresh(app):
    """读输入 JSON 并重画可视化区。"""
    canvas = getattr(app, "vp_canvas", None)
    if canvas is None:
        return []
    app.vp_fix_notice = ""          # 换了输入，上次的修正提示作废
    notes = []
    try:
        notes = (app.get_input_data() or {}).get("notes") or []
    except Exception:
        notes = []
    states = _state_list(app, notes)
    app.vp_notes = notes
    draw(app, notes, states)
    return notes


# ----------------------------------------------------------------------
# 绘制
# ----------------------------------------------------------------------
def _time_bounds_beats(app, notes):
    """时间范围由输入的音符决定（单位：拍）。"""
    times = []
    for note in notes:
        times.append(app.time_to_float(note.get("startTime", [0, 0, 1])))
        times.append(app.time_to_float(note.get("endTime", note.get("startTime", [0, 0, 1]))))
    if not times:
        return 0.0, 1.0
    return min(times), max(times)


def _x_map(width, pad):
    """x 坐标 → 画布横坐标的映射函数（±675 铺满可用宽度）。"""
    usable = max(1.0, width - 2 * pad)

    def to_px(position_x):
        return pad + (float(position_x) + COORD_HALF) / (COORD_HALF * 2.0) * usable

    return to_px, usable / (COORD_HALF * 2.0)


def _grid_step(px_per_beat, min_px):
    """挑一个使网格不至于太密的拍数步长。"""
    for step in (0.125, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0):
        if step * px_per_beat >= min_px:
            return step
    return 64.0


def _format_beat(value):
    return ("%g" % round(value, 4)) if value else "0"


def draw(app, notes, states):
    canvas = app.vp_canvas
    _close_editor(app)
    canvas.delete("all")
    width = max(canvas.winfo_width(), app.px(320))
    height = max(canvas.winfo_height(), app.px(160))
    pad = app.px(6)
    to_px, unit_px = _x_map(width, pad)
    note_w_px = NOTE_WIDTH * unit_px

    if not notes:
        canvas.create_text(width / 2, height / 2, text=t("labels.no_notes"), fill="#888888")
        canvas.configure(scrollregion=(0, 0, width, height))
        return

    t0, t1 = _time_bounds_beats(app, notes)
    # 上下各留一拍，音符上的文字才不会被裁掉
    t_hi = t1 + TIME_PAD_BEATS
    t_lo = t0 - TIME_PAD_BEATS
    span = max(t_hi - t_lo, 0.25)
    zoom = max(0.2, float(getattr(app, "vp_zoom", 1.0)))
    usable_h = max(app.px(60), height - 2 * pad)
    px_per_beat = usable_h / span * zoom
    content_h = span * px_per_beat + 2 * pad
    scroll = max(0.0, min(float(getattr(app, "vp_scroll", 0.0)), max(0.0, content_h - height)))

    def to_py(beats):
        # 下方 = 较早时间，上方 = 较晚时间
        return pad + (t_hi - beats) * px_per_beat - scroll

    grid_color = "#d8d8d8" if app.theme_name == "light" else "#3a3a3a"
    muted = "#999999"

    # 时间网格（单位：拍）
    step = _grid_step(px_per_beat, app.px(18))
    tick = math.floor(t_lo / step) * step
    while tick <= t_hi + step:
        y = to_py(tick)
        if -20 <= y <= height + 20:
            canvas.create_line(pad, y, width - pad, y, fill=grid_color)
            canvas.create_text(pad + 2, y, anchor="w", text=_format_beat(tick),
                               fill=muted, font=app.font_spec(7))
        tick += step

    # 中线（x = 0）与 ±675 边界
    mid = to_px(0)
    canvas.create_line(mid, 0, mid, content_h, fill=grid_color, dash=(2, 3))
    for edge in (-COORD_HALF, COORD_HALF):
        ex = to_px(edge)
        canvas.create_line(ex, 0, ex, content_h, fill=grid_color)

    for index, note in enumerate(notes):
        state = states[index] if index < len(states) else {}
        note_type = int(note.get("type", 1))
        color = TYPE_COLORS.get(note_type, "#aaaaaa")
        position_x = note.get("positionX", 0.0) or 0.0
        x0 = to_px(position_x) - note_w_px / 2.0
        x1 = x0 + note_w_px

        b0 = app.time_to_float(note.get("startTime", [0, 0, 1]))
        b1 = max(app.time_to_float(note.get("endTime", note.get("startTime", [0, 0, 1]))), b0)
        # 翻转后：较早时间 → y 较大
        y_bottom = to_py(b0)
        y_top = min(to_py(b1), y_bottom - app.px(4))
        if y_top > height + 30 or y_bottom < -30:
            continue

        hover = index == getattr(app, "vp_selected", None)
        tags = ("note", str(index))
        if note_type == 2:                        # hold 画空心框
            canvas.create_rectangle(x0, y_top, x1, y_bottom, outline=color, fill="",
                                    width=3 if hover else 2, tags=tags)
        else:
            canvas.create_rectangle(x0, y_top, x1, y_bottom, fill=color,
                                    outline=color if hover else "", width=3 if hover else 0,
                                    tags=tags)

        # 音高·数量标在音符**上方**（放右边会在靠右边缘时跑到框外）
        pitch = note_pitch(state)
        text = "%s\u00b7%d" % (pitch, effective_count(app, note, state))
        if state.get("glide"):
            text = "%s\u2192%s\u00b7%d" % (pitch, state.get("pitch2", "0"),
                                           effective_count(app, note, state))
        canvas.create_text((x0 + x1) / 2.0, y_top - app.px(1), anchor="s",
                           text=text, fill=color, font=app.font_spec(8),
                           tags=("pitch", str(index)))

    # 供播放进度线换算用：把「拍 → y」的映射记下来
    app.vp_time_map = {"t_hi": t_hi, "px_per_beat": px_per_beat, "scroll": scroll, "pad": pad}

    # 输入里有非法音符时给一条提示（转换后才会出现）
    notice = getattr(app, "vp_fix_notice", "")
    if notice:
        canvas.create_text(width / 2.0, app.px(10), anchor="n", text=notice,
                           fill="#e03131", font=app.font_spec(8), tags=("notice",))

    canvas.configure(scrollregion=(0, 0, width, max(height, content_h)))
    _draw_progress(app)


# ----------------------------------------------------------------------
# 播放进度线（覆盖在预览窗上，随时间从下往上移动）
# ----------------------------------------------------------------------
def _time_map_to_y(app, beats):
    m = getattr(app, "vp_time_map", None)
    if not m:
        return None
    return m["pad"] + (m["t_hi"] - beats) * m["px_per_beat"] - m["scroll"]


def _progress_beat(app, elapsed):
    play = getattr(app, "vp_play", None)
    if not play:
        return None
    duration = max(1e-6, play["duration"])
    ratio = min(1.0, max(0.0, elapsed / duration))
    return play["beat_from"] + ratio * (play["beat_to"] - play["beat_from"])


def _draw_progress(app):
    """按当前 elapsed 画/更新那条进度线（只在播放中）。"""
    play = getattr(app, "vp_play", None)
    if not play:
        return
    canvas = getattr(app, "vp_canvas", None)
    if canvas is None:
        return
    beat = _progress_beat(app, time.monotonic() - play["start"])
    y = _time_map_to_y(app, beat)
    width = max(canvas.winfo_width(), app.px(320))
    color = theme.palette(app.theme_name).get("accent", "#ff6b00")
    item = play.get("item")
    if item is None or not canvas.type(item):
        play["item"] = canvas.create_line(0, y, width, y, fill=color, width=2,
                                          tags=("progress",))
    else:
        canvas.coords(item, 0, y, width, y)
    try:
        canvas.tag_raise(play["item"])
    except Exception:
        pass


def _tick_progress(app):
    """定时把进度线往前推（窗口销毁等异常一律吞掉并停表）。"""
    play = getattr(app, "vp_play", None)
    if not play:
        return
    try:
        elapsed = time.monotonic() - play["start"]
        if elapsed >= play["duration"]:
            _stop_progress(app)
            return
        _draw_progress(app)
    except Exception:
        _stop_progress(app)
        return
    try:
        app.root.after(40, lambda: _tick_progress(app))
    except Exception:
        pass


def _start_progress(app, duration, beat_from, beat_to):
    _stop_progress(app)
    app.vp_play = {"start": time.monotonic(), "duration": max(0.05, duration),
                   "beat_from": beat_from, "beat_to": beat_to, "item": None}
    _draw_progress(app)
    try:
        app.root.after(40, lambda: _tick_progress(app))
    except Exception:
        pass


def _stop_progress(app):
    play = getattr(app, "vp_play", None)
    canvas = getattr(app, "vp_canvas", None)
    if play and canvas is not None:
        item = play.get("item")
        if item is not None:
            try:
                if canvas.type(item):
                    canvas.delete(item)
            except Exception:
                pass
    app.vp_play = None


# ----------------------------------------------------------------------
# 交互
# ----------------------------------------------------------------------
def scroll_canvas(app, event):
    """滚轮：只滚动时间轴。"""
    step = app.px(40) * (1 if event.delta < 0 else -1)
    height = max(app.vp_canvas.winfo_height(), app.px(160))
    try:
        content_h = float(app.vp_canvas.cget("scrollregion").split()[3])
    except Exception:
        content_h = height
    app.vp_scroll = max(0.0, min(float(app.vp_scroll) + step, max(0.0, content_h - height)))
    draw(app, getattr(app, "vp_notes", []), getattr(app, "vp_states", []))


def zoom_canvas(app, event):
    """Ctrl + 滚轮：只缩放时间轴。"""
    step = 0.15 if event.delta > 0 else -0.15
    app.vp_zoom = min(20.0, max(0.5, float(getattr(app, "vp_zoom", 1.0)) + step))
    draw(app, getattr(app, "vp_notes", []), getattr(app, "vp_states", []))


def click_canvas(app, event, right=False):
    """左键点音符 → 就地改音高；右键：hold 改「结束音调」，其余改数量。都不弹窗。

    点空白处先提交当前编辑框再取消选中（不按回车也不会丢）。
    """
    notes = getattr(app, "vp_notes", [])
    states = getattr(app, "vp_states", [])
    if not notes:
        return
    hit = _hit_index(app, event)
    if hit is None:
        _commit_editor(app)              # 点空白 = 提交，而不是丢弃
        app.vp_selected = None
        draw(app, notes, states)
        return
    note = notes[hit]
    is_hold = int(note.get("type", 1)) == 2
    app.vp_selected = hit
    _commit_editor(app)
    draw(app, notes, states)

    if right and is_hold:
        # 右键 hold：改结束音调（留空即非滑音）
        _open_editor(app, hit, kind="tail")
    elif right:
        # 右键其它：直接改音符数量
        _open_editor(app, hit, kind="count")
    else:
        _open_editor(app, hit, kind="main")


def _hit_index(app, event):
    """点到的音符下标：先看画布图元，再退化成按 y 找最近的一个。"""
    canvas = app.vp_canvas
    for item in canvas.find_overlapping(event.x - 3, event.y - 3, event.x + 3, event.y + 3):
        for tag in canvas.gettags(item):
            if tag.isdigit():
                index = int(tag)
                if index < len(getattr(app, "vp_notes", [])):
                    return index
    best, best_dy = None, None
    for item in canvas.find_all():
        tags = canvas.gettags(item)
        if not any(tag.isdigit() for tag in tags):
            continue
        bbox = canvas.bbox(item)
        if not bbox:
            continue
        index = int([tag for tag in tags if tag.isdigit()][0])
        if event.x < bbox[0] - 120 or event.x > bbox[2] + 120:
            continue
        dy = 0 if bbox[1] <= event.y <= bbox[3] else min(abs(event.y - bbox[1]),
                                                         abs(event.y - bbox[3]))
        if best_dy is None or dy < best_dy:
            best, best_dy = index, dy
    return best


# ----------------------------------------------------------------------
# 画布上原地编辑（不弹出新窗口）
# ----------------------------------------------------------------------
def _close_editor(app):
    entry = getattr(app, "vp_editor", None)
    if entry is not None:
        try:
            entry.destroy()
        except Exception:
            pass
    app.vp_editor = None
    app.vp_editor_item = None
    app.vp_editor_index = None


def _editor_initial(app, index, kind):
    """编辑框的初始文字（留空对 tail 表示非滑音，所以 tail 在非滑音时就是空的）。"""
    state = getattr(app, "vp_states", [])[index]
    note = getattr(app, "vp_notes", [])[index]
    pitch = note_pitch(state)
    if kind == "tail":
        return state.get("pitch2", "") if state.get("glide") else ""
    if kind == "count":
        count = state.get("count", 1)
        if int(note.get("type", 1)) == 2:      # hold 的数量是推算出来的，显示出来只作参考
            return str(effective_count(app, note, state))
        return str(count) if count else "1"
    if state.get("glide"):
        return "%s\u2192%s" % (pitch, state.get("pitch2", "0"))
    if pitch != "0":
        return pitch
    count = effective_count(app, note, state)
    return str(count) if count > 1 else "0"


def _open_editor(app, index, kind="main"):
    """在音符标签所在的位置内嵌一个输入框，光标直接落在这里。

    kind: main = 音高（滑音写 A→B）；count = 数量；tail = hold 的结束音调（留空 = 非滑音）
    """
    canvas = app.vp_canvas
    _close_editor(app)
    st = getattr(app, "vp_states", [])
    ns = getattr(app, "vp_notes", [])
    if index >= len(st) or index >= len(ns):
        return
    # 找到该音符标签图元的位置
    anchor = None
    for item in canvas.find_withtag("pitch"):
        if str(index) in canvas.gettags(item):
            anchor = canvas.bbox(item)
            break
    width = max(canvas.winfo_width(), app.px(320))
    pad = app.px(6)
    if anchor:
        cx = (anchor[0] + anchor[2]) / 2.0
        cy = anchor[1] - app.px(1)
    else:
        cx, cy = width / 2.0, canvas.winfo_height() / 2.0
    half = app.px(46)
    cx = min(max(cx, pad + half), width - pad - half)
    if cy < app.px(24):                       # 顶到上边就改放在音符下方
        cy = min(cy + app.px(26), canvas.winfo_height() - app.px(4))
        anchor_side = "n"
    else:
        anchor_side = "s"

    palette = theme.palette(app.theme_name)
    entry = tk.Entry(canvas, font=app.font_spec(9), width=10, justify="center",
                     bg=palette["text_bg"], fg=palette["text_fg"],
                     insertbackground=palette["text_fg"], relief=tk.FLAT, bd=0,
                     highlightthickness=1, highlightbackground=palette["accent"],
                     highlightcolor=palette["accent"])
    entry.insert(0, _editor_initial(app, index, kind))
    entry.select_range(0, tk.END)
    item = canvas.create_window(cx, cy, window=entry, anchor=anchor_side, tags=("editor",))
    app.vp_editor = entry
    app.vp_editor_item = item
    app.vp_editor_index = index
    app.vp_editor_kind = kind
    # 记一下「这一下点击就是刚打开编辑框的那次」，别被 toplevel 上的兜底提交立刻关掉。
    # 同一个点击事件的所有绑定是同步依次触发的，所以用 after_idle 在本次事件结束后清除。
    app.vp_editor_fresh = True
    try:
        app.root.after_idle(lambda: setattr(app, "vp_editor_fresh", False))
    except Exception:
        app.vp_editor_fresh = False
    entry.bind("<Return>", lambda e: _commit_editor(app))
    entry.bind("<KP_Enter>", lambda e: _commit_editor(app))
    entry.bind("<Escape>", lambda e: _cancel_editor(app))
    entry.bind("<FocusOut>", lambda e: _commit_editor(app))
    # 提示语：告诉用户这个框在改什么、留空意味着什么
    hint = {"count": t("labels.count_box_hint"),
            "tail": t("labels.glide_tail_hint")}.get(kind)
    if hint and hasattr(app, "_update_status_text"):
        app._update_status_text(hint)
    try:
        entry.focus_set()
    except Exception:
        pass


def _on_root_click(app, event):
    """点窗口里任何地方都先提交当前编辑（不按回车也不丢）。

    控件自身的绑定先于 toplevel 触发，所以画布点击已经处理过一轮；
    这里只在「编辑框还开着、且点的不是编辑框本身」时兜底提交。
    """
    editor = getattr(app, "vp_editor", None)
    if editor is None:
        return
    if event is not None and getattr(event, "widget", None) is editor:
        return
    if getattr(app, "vp_editor_fresh", False):     # 这一下点击刚刚打开的新编辑框
        app.vp_editor_fresh = False
        return
    _commit_editor(app)


def _commit_editor(app):
    """把编辑框内容写入状态并关闭。按用途分流：
    main → 音高 / 滑音 / （非 hold）数量；count → 数量；tail → 结束音调（留空 = 非滑音）。
    """
    entry = getattr(app, "vp_editor", None)
    if entry is None:
        return
    index = getattr(app, "vp_editor_index", None)
    kind = getattr(app, "vp_editor_kind", "main")
    try:
        text = entry.get()
    except Exception:
        text = ""
    states = getattr(app, "vp_states", [])
    notes = getattr(app, "vp_notes", [])
    if index is not None and index < len(states) and index < len(notes):
        state = states[index]
        note = notes[index]
        is_hold = int(note.get("type", 1)) == 2
        if kind == "tail":
            parsed = parse_pitch(text)
            if (text or "").strip() == "":
                state["glide"] = False            # 留空 → 非滑音
                state["pitch2"] = "0"
            elif parsed:
                state["glide"] = True
                state["pitch2"] = parsed
        elif kind == "count":
            try:
                state["count"] = max(1, int((text or "").strip()))
            except ValueError:
                pass
        else:
            pitch, pitch2, count = parse_edit(text)
            if pitch is not None:
                state["pitch"] = pitch
            if pitch2 is not None and is_hold:
                state["glide"] = True
                state["pitch2"] = pitch2
            elif pitch is not None:
                state["glide"] = False
            if count is not None and not is_hold:
                state["count"] = count
    _close_editor(app)
    draw(app, notes, states)
    if hasattr(app, "_update_status_text"):
        app._update_status_text()      # 恢复功能介绍


def _cancel_editor(app):
    _close_editor(app)
    draw(app, getattr(app, "vp_notes", []), getattr(app, "vp_states", []))
    if hasattr(app, "_update_status_text"):
        app._update_status_text()


# ----------------------------------------------------------------------
# 预览（锯齿波）
# ----------------------------------------------------------------------
def _note_preview_span(app, note, state):
    """一个音符在预览里发声多久（秒）。

    * hold ：就是它自己的时长；
    * 其它 ：**严格由数量推算** —— 输出里会补出「数量」个音符、每个间隔一个单音符时值，
             所以发声长度 = 数量 × 单音符时值（音高 0 时单音符时值退回一个 16 分音）。
             这里刻意不加"最小 10ms"之类的下限，否则数量少的时候就不再等于数量×时值了。
    """
    bpm = _bpm(app)
    t0 = app.time_to_float(note.get("startTime", [0, 0, 1])) * 60.0 / bpm
    t1 = app.time_to_float(note.get("endTime", note.get("startTime", [0, 0, 1]))) * 60.0 / bpm
    t1 = max(t1, t0)
    if int(note.get("type", 1)) == 2:
        return max(0.005, t1 - t0)
    count = effective_count(app, note, state)
    return max(1.0 / 44100.0, count * unit_seconds(app, note_pitch(state)))


def _samples_for(app, notes, states, sample_rate=44100):
    """把整段谱面渲染成锯齿波样本；返回 (样本, 采样率, 时长秒, 起始拍, 结束拍)。

    为了让「点预览就能马上听到」，时间轴会**平移到第一个发声的音符**：
    否则片段起始拍数很大时（例如第 100 小节）前面全是静音，
    既慢（要分配几十兆的缓冲）又白等。
    """
    bpm = _bpm(app)
    beats_per_second = bpm / 60.0
    timeline = []
    for index, note in enumerate(notes):
        state = states[index] if len(states) > index else {}
        pitch = note_pitch(state)
        freq = pitch_frequency(pitch)
        if freq is None:
            continue
        t0 = app.time_to_float(note.get("startTime", [0, 0, 1])) / beats_per_second
        length = _note_preview_span(app, note, state)
        freq_end = freq
        if state.get("glide"):
            freq_end = pitch_frequency(state.get("pitch2", "0")) or freq
        timeline.append((t0, length, freq, freq_end))

    if not timeline:
        return [], sample_rate, 0.0, 0.0, 0.0

    t_first = min(item[0] for item in timeline)
    t_last = max(item[0] + item[1] for item in timeline)
    total_span = max(0.05, t_last - t_first)
    beat_from = t_first * beats_per_second
    beat_to = t_last * beats_per_second

    total_samples = int((total_span + 0.08) * sample_rate)
    buffer = [0] * total_samples
    amplitude = 0.32
    limit = 32767
    fade_samples = max(1.0, 0.003 * sample_rate)
    for t0, length, freq, freq_end in timeline:
        start = int((t0 - t_first) * sample_rate)
        count = int(length * sample_rate)
        if count <= 0:
            continue
        phase = 0.0
        step = (freq_end - freq) / float(count) if count > 1 else 0.0
        cur = freq
        for i in range(count):
            pos = start + i
            if pos >= total_samples:
                break
            phase += cur / float(sample_rate)
            phase -= math.floor(phase)
            cur += step
            if phase < 0.0:                       # 浮点兜底
                phase = 0.0
            wave = 2.0 * phase - 1.0               # 锯齿波
            fade = min(1.0, i / fade_samples, (count - i) / fade_samples)
            value = buffer[pos] + int(32767 * amplitude * wave * fade)
            buffer[pos] = limit if value > limit else (-limit if value < -limit else value)
    return buffer, sample_rate, total_span, beat_from, beat_to


def _preview_key(app, notes, states):
    """预览缓存键：内容没变就不用重新合成（合成是逐样本的纯 Python 循环）。"""
    bpm = _bpm(app)
    parts = [bpm]
    for index, note in enumerate(notes):
        state = states[index] if len(states) > index else {}
        parts.append((
            app.time_to_float(note.get("startTime", [0, 0, 1])),
            app.time_to_float(note.get("endTime", note.get("startTime", [0, 0, 1]))),
            int(note.get("type", 1)),
            note_pitch(state),
            state.get("pitch2") if state.get("glide") else None,
            1 if state.get("glide") else 0,
            state.get("count", 1),
        ))
    return tuple(parts)


def preview(app):
    """预览：整段按音高合成锯齿波并播放，同时在预览窗上画一条播放进度线。"""
    notes = getattr(app, "vp_notes", [])
    states = getattr(app, "vp_states", [])
    if not notes:
        notes = refresh(app)
        states = getattr(app, "vp_states", [])
    if not notes:
        return False

    key = _preview_key(app, notes, states)
    cache = getattr(app, "vp_preview_cache", None)
    if cache and cache.get("key") == key and cache.get("path") and os.path.exists(cache["path"]):
        # 内容没变：直接播上次渲染好的文件（省掉整段重新合成）
        path, duration, beats = cache["path"], cache["duration"], cache["beats"]
    else:
        samples, rate, duration, beat_from, beat_to = _samples_for(app, notes, states)
        if not samples:
            return False
        path = audio.render_wav(samples, rate)
        if not path:
            return False
        beats = (beat_from, beat_to)
        app.vp_preview_cache = {"key": key, "path": path, "duration": duration, "beats": beats}

    if not audio.play(None, path):
        return False
    _start_progress(app, duration, beats[0], beats[1])
    return True


def stop_preview(app):
    _stop_progress(app)
    audio.stop()


# ----------------------------------------------------------------------
# 转换
# ----------------------------------------------------------------------
def _glide_boundaries(app, note, pitch, pitch2, count):
    """滑音：按「瞬时重复频率线性变化」反解出每个音符的时间点（秒，相对该音符起点）。

    ∫₀ᵗ f(τ)dτ = k，f(τ) = f1 + (f2-f1)·τ/T  ⇒  a·t² + b·t - k = 0
    """
    span = _seconds(app, note)
    f1 = pitch_frequency(pitch) or 0.0
    f2 = pitch_frequency(pitch2) or f1
    boundaries = [0.0]
    if span <= 0:
        return [0.0]
    a = (f2 - f1) / (2.0 * span)
    b = f1
    for k in range(1, count):
        if abs(a) < 1e-12:
            t = k / b if b > 0 else span * k / float(count)
        else:
            disc = b * b + 4.0 * a * k
            disc = max(0.0, disc)
            t = (-b + math.sqrt(disc)) / (2.0 * a)
        boundaries.append(min(max(t, 0.0), span))
    boundaries.append(span)                    # 最后一段一定收在原 endTime
    return boundaries


def process(app, data):
    """把每个音符按音高拆成纵连。

    hold ：数量由 bpm 与音高推算，沿时长切分成这么多个音符，**彼此首尾相接**
           （第 1 个的 endTime = 第 2 个的 startTime）；滑音则按频率变化不均匀分布
    其余 ：第 1 个保持原位，其后每隔「单音符时值」补一个（数量手填）
    """
    notes = data.get("notes") or []
    states = _state_list(app, notes)

    fill = app.vp_fill_var.get() if hasattr(app, "vp_fill_var") else ""
    same_as_input = (fill == t("labels.fill_same_as_input")) or (fill not in NAME_TYPES)
    fill_type = NAME_TYPES.get(fill)
    beats_per_second = _bpm(app) / 60.0

    result = []
    for index, note in enumerate(notes):
        state = states[index] if index < len(states) else {}
        note_type = int(note.get("type", 1))
        pitch = note_pitch(state)
        out_type = note_type if same_as_input else (fill_type or note_type)

        start = app.time_to_float(note.get("startTime", [0, 0, 1]))
        end = max(app.time_to_float(note.get("endTime", note.get("startTime", [0, 0, 1]))), start)
        count = effective_count(app, note, state)

        if note_type == 2 and end > start and count > 1:
            # hold：整段等分（或按滑音变频）成 count 个 hold，首尾相接
            # marks 一律用「相对起点的拍数」表示，最后一段一定收在原 endTime
            if state.get("glide"):
                # _glide_boundaries 返回秒，换算成拍
                marks = [x * beats_per_second
                         for x in _glide_boundaries(app, note, pitch, state.get("pitch2"), count)]
            else:
                span = end - start
                marks = [span * k / float(count) for k in range(count + 1)]
            for step in range(count):
                piece = dict(note)
                piece["type"] = out_type
                piece["startTime"] = app.float_to_time(start + marks[step])
                piece["endTime"] = app.float_to_time(start + marks[step + 1])
                result.append(piece)
            continue

        # 其余：第 1 个保持原位，其后沿时间轴每隔 unit 补一个
        first = dict(note)
        first["type"] = out_type
        result.append(first)
        if count <= 1:
            continue
        unit = unit_beats(app, pitch)
        if unit <= 0:
            continue
        for step in range(1, count):
            moment = start + unit * step
            piece = dict(note)
            piece["type"] = out_type
            piece["startTime"] = app.float_to_time(moment)
            piece["endTime"] = app.float_to_time(moment)
            result.append(piece)

    result.sort(key=lambda n: app.time_to_float(n.get("startTime", [0, 0, 1])))

    # 兜底规范化：输入里若有 endTime 早于 startTime 的音符（外部工具/手改 JSON 都可能留下），
    # 原样复制就会让导出的 JSON 变成非法谱面。这里统一按「零长度」修正并给用户一条提示。
    fixed = 0
    for piece in result:
        s = app.time_to_float(piece.get("startTime", [0, 0, 1]))
        e = app.time_to_float(piece.get("endTime", piece.get("startTime", [0, 0, 1])))
        if e < s:
            piece["endTime"] = app.float_to_time(s)
            fixed += 1
    app.vp_fixed_invalid = fixed
    if fixed:
        app.vp_fix_notice = t("labels.fixed_invalid_end", n=fixed)
        try:
            sys.stderr.write("vertical_pitch: %d 个音符的 endTime 早于 startTime，已按零长度修正\n" % fixed)
        except Exception:
            pass
    else:
        app.vp_fix_notice = ""

    data["notes"] = result
    return data
