# -*- coding: utf-8 -*-
"""需求十二验证：非线性切割贝塞尔优化 / 事件类型转换“→” / 矫正颜色染色反推 / 旧版染色标签隐藏"""
import copy
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import tkinter as tk

from rpe_toolbox.app import RPEToolbox

# 模组化后，颜色矫正算法属于"图片转音符画"模组，直接从模组模块取
from rpe_toolbox import mods_loader  # noqa: E402

IMG = mods_loader.find("image_to_notes").module

root = tk.Tk()
root.withdraw()
app = RPEToolbox(root)

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


def near(a, b, eps=1e-6):
    return abs(a - b) < eps


# ---- 测试J: 非线性切割组合效果与原曲线一致（第57拍曲线） ----
orig_pts = [0.33, 1.45, 0.22, -0.32]
ev = {"bezier": 1, "bezierPoints": orig_pts, "easingLeft": 0.0, "easingRight": 1.0,
      "easingType": 1, "end": 450.0, "endTime": [58, 0, 1], "start": -450.0, "startTime": [57, 0, 1], "type": 2}
segs = app.func_nonlinear_split({"events": [copy.deepcopy(ev)]}, 16)["events"]
check("J 切成 4 段", len(segs) == 4, str(len(segs)))


def seg_value_at(seg, t):
    t0 = app.time_to_float(seg["startTime"])
    t1 = app.time_to_float(seg["endTime"])
    p = (t - t0) / (t1 - t0)
    return app.interpolate_value(seg["start"], seg["end"], p, seg.get("easingType", 1),
                                 seg.get("bezier", 0), seg.get("bezierPoints", [0, 0, 0, 0]))


worst = 0.0
for i in range(65):
    t = 57.0 + i / 64.0
    orig = app.interpolate_value(-450.0, 450.0, t - 57.0, 1, 1, orig_pts)
    for seg in segs:
        if app.time_to_float(seg["startTime"]) - 1e-9 <= t <= app.time_to_float(seg["endTime"]) + 1e-9:
            worst = max(worst, abs(orig - seg_value_at(seg, t)))
            break
check("J 组合效果偏差 < 3（优化前为 162）", worst < 3.0, "worst=%.3f" % worst)

# 边界值仍精确
boundary = segs[1]["start"]
exact = app.interpolate_value(-450.0, 450.0, 0.25, 1, 1, orig_pts)
check("J 段边界值精确", near(boundary, exact, 1e-6), "%.4f vs %.4f" % (boundary, exact))

# ---- 测试K: 矫正颜色染色 = 反推最接近结果 ----
app.note_type_var.set("drag")  # 固定色 [240, 237, 105]
check("K 白像素 -> tint 全255", IMG._corrected_color_from_rgb(app, 255, 255, 255) == [255, 255, 255],
      str(IMG._corrected_color_from_rgb(app, 255, 255, 255)))
check("K 黑像素 -> tint 全0", IMG._corrected_color_from_rgb(app, 0, 0, 0) == [0, 0, 0],
      str(IMG._corrected_color_from_rgb(app, 0, 0, 0)))
tint_mid = IMG._corrected_color_from_rgb(app, 120, 120, 120)
check("K 灰像素反推 [128,129,255]", tint_mid == [128, 129, 255], str(tint_mid))


def multiply_forward(fixed, tint):
    return [min(255, max(0, round(f * t / 255.0))) for f, t in zip(fixed, tint)]


rendered = multiply_forward([240, 237, 105], tint_mid)
check("K 反推后正片叠底渲染最接近目标", rendered == [120, 120, 105], str(rendered))

# ---- 测试L: UI —— 不透明度替代亮度隐藏旧版染色标签；事件类型转换含“→” ----
app.color_mode_var.set("不透明度替代亮度")
check("L 不透明度替代亮度隐藏旧版染色标签", app.legacy_tint_check.winfo_manager() == "",
      "manager=%s" % app.legacy_tint_check.winfo_manager())
app.color_mode_var.set("染色")
check("L 染色模式恢复旧版染色标签", app.legacy_tint_check.winfo_manager() == "pack",
      "manager=%s" % app.legacy_tint_check.winfo_manager())


def count_arrows(frame):
    n = 0
    for child in frame.winfo_children():
        try:
            # 界面已统一为 ttk 控件（配合 sv-ttk 主题），ttk.Label 的 winfo_class 为 TLabel
            if child.winfo_class() in ("Label", "TLabel") and child.cget("text") == "\u2192":
                n += 1
        except Exception:
            pass
        n += count_arrows(child)
    return n


arrows = count_arrows(app.frame_event_convert)
check("L 事件类型转换行含 →（≥9 处）", arrows >= 9, "arrows=%d" % arrows)

print("=" * 50)
print("TOTAL: %d PASS, %d FAIL" % (ok, fail))
root.destroy()
sys.exit(1 if fail else 0)
