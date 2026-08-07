# -*- coding: utf-8 -*-
"""UI 功能切换验证：验证 on_function_change 对每个功能键不报错，且输入框隐藏逻辑正确"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import tkinter as tk

from rpe_toolbox.app import RPEToolbox
from rpe_toolbox import resources

root = tk.Tk()
root.withdraw()
app = RPEToolbox(root)

# 功能键 -> 标签
funcs = {
    "hold_notes_connect": "1. hold/事件首尾相接",
    "nonlinear_split": "2. 非线性切割",
    "polar_conversion": "3. 极坐标转换",
    "event_type_convert": "4. 事件类型转换",
    "image_to_notes": "5. 图片转音符画",
    "time_interval_to_yoffset": "6. 时间间隔转y偏移",
    "reverse_data": "7. 倒序/拉伸",
    "midi_bpm_extract": "8. MIDI BPM 提取",
}

ok = 0
fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print("PASS:", name)
    else:
        fail += 1
        print("FAIL:", name, detail)


for key, label in funcs.items():
    try:
        app.current_function.set(label)
        app.on_function_change()
        check("切换 %s" % key, True)
    except Exception as e:
        check("切换 %s" % key, False, repr(e))

# 验证输入框隐藏逻辑
app.current_function.set(funcs["image_to_notes"])
app.on_function_change()
mapped = app.functions.get(app.current_function.get(), (None, ""))[0]
check("UI 图片模式隐藏输入框", mapped == "image_to_notes" and app.input_frame.winfo_manager() == "", "manager=%s" % app.input_frame.winfo_manager())
app.current_function.set(funcs["midi_bpm_extract"])
app.on_function_change()
check("UI MIDI 模式隐藏输入框", app.input_frame.winfo_manager() == "", "manager=%s" % app.input_frame.winfo_manager())
app.current_function.set(funcs["hold_notes_connect"])
app.on_function_change()
check("UI hold 模式显示输入框", app.input_frame.winfo_manager() == "pack", "manager=%s" % app.input_frame.winfo_manager())

# 需求十一：曲线drag 选择非“无”时显示音符间隔输入行
app.current_function.set(funcs["event_type_convert"])
app.on_function_change()
app.drag_mode_var.set("X轴位移与缩放")
check("UI 曲线drag显示音符间隔行", app.frame_drag_interval.winfo_manager() != "", "manager=%s" % app.frame_drag_interval.winfo_manager())
app.drag_mode_var.set("无")
check("UI 曲线drag为无时隐藏音符间隔行", app.frame_drag_interval.winfo_manager() == "", "manager=%s" % app.frame_drag_interval.winfo_manager())
check("UI 定轨hold默认无", app.hold_mode_var.get() == "无", app.hold_mode_var.get())
check("UI 窗口图标优先 mini ico-z1.png", resources.find_icon() is not None and resources.find_icon().endswith("mini ico-z1.png"), str(resources.find_icon()))
check("UI exe 图标源为完整版 ico-z1.png", resources.find_full_icon() is not None and resources.find_full_icon().endswith("ico-z1.png"), str(resources.find_full_icon()))

# 验证 process_data 在图片模式下不报错（无输入框内容）
app.current_function.set(funcs["image_to_notes"])
app.on_function_change()
app.image_path_var.set(os.path.join(BASE, "assets", "images", "_test_img_alpha.png"))
app.process_data()
out = app.text_output.get("1.0", tk.END).strip()
check("UI 图片模式 process_data", out.startswith("{") and "tint" in out, out[:80])

print("=" * 50)
print("TOTAL: %d PASS, %d FAIL" % (ok, fail))
root.destroy()
sys.exit(1 if fail else 0)
