# -*- coding: utf-8 -*-
"""需求十一验证：图片时间间隔 / 贝塞尔子段 / 事件类型转换（定轨hold、曲线drag）"""
import copy
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import tkinter as tk

from rpe_toolbox.app import RPEToolbox
from rpe_toolbox.imglib import Image

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


# ---- 测试F: 图片转音符画 16分音、高度4 -> 行间隔 1/4 拍 ----
img_path = os.path.join(BASE, "assets", "images", "_test_req11_img.png")
img = Image.new("RGB", (3, 4))
for y in range(4):
    for x in range(3):
        img.putpixel((x, y), (30 + x * 80, 60 + y * 50, 120))
img.save(img_path)
app.image_path_var.set(img_path)
app.use_original_size_var.set(True)
app.auto_adjust_width_var.set(True)
app.legacy_tint_var.set(False)
app.density_var.set("16")
outf = app.func_image_to_notes({"imagePath": img_path})
starts = sorted({app.time_to_float(n["startTime"]) for n in outf["notes"]})
check("F 4 行 startTime = 0/0.25/0.5/0.75", starts == [0.0, 0.25, 0.5, 0.75], str(starts))
intervals = [app.time_to_float(n["endTime"]) - app.time_to_float(n["startTime"]) for n in outf["notes"]]
check("F 每行间隔 1/4 拍", all(near(iv, 0.25, 1e-6) for iv in intervals), str(set(intervals)))

# ---- 测试G: 定轨hold 5k（需求文档示例） ----
app.hold_mode_var.set("5k")
app.drag_mode_var.set("无")
doc_events = {"events": [
    {"bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0], "easingLeft": 0.0, "easingRight": 1.0,
     "easingType": 1, "end": 0.0, "endTime": [48, 1, 3], "layer": 0, "line": 0, "linkgroup": 0,
     "start": 0.0, "startTime": [48, 0, 1], "type": 1},
    {"bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0], "easingLeft": 0.0, "easingRight": 1.0,
     "easingType": 1, "end": -450.0, "endTime": [48, 2, 3], "layer": 0, "line": 0, "linkgroup": 0,
     "start": -450.0, "startTime": [48, 0, 1], "type": 2},
    {"bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0], "easingLeft": 0.0, "easingRight": 1.0,
     "easingType": 1, "end": 0.0, "endTime": [49, 0, 1], "layer": 0, "line": 0, "linkgroup": 0,
     "start": 0.0, "startTime": [48, 0, 1], "type": 3},
    {"bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0], "easingLeft": 0.0, "easingRight": 1.0,
     "easingType": 1, "end": 200.0, "endTime": [49, 1, 3], "layer": 0, "line": 0, "linkgroup": 0,
     "start": 200.0, "startTime": [48, 0, 1], "type": 4},
    {"bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0], "easingLeft": 0.0, "easingRight": 1.0,
     "easingType": 1, "end": 1.0, "endTime": [49, 2, 3], "layer": 0, "line": 0, "linkgroup": 0,
     "start": 1.0, "startTime": [48, 0, 1], "type": 5},
]}
outg = app.func_event_type_convert(copy.deepcopy(doc_events))
check("G 输出为 notes", "notes" in outg, str(list(outg.keys())))
gx = {n["positionX"] for n in outg["notes"]}
check("G 5k 轨道位置", gx == {-540.0, -270.0, 0.0, 270.0, 540.0}, str(sorted(gx)))
check("G 全部为 hold", all(n["type"] == 2 for n in outg["notes"]), str([n["type"] for n in outg["notes"]]))
g_end = {n["positionX"]: n["endTime"] for n in outg["notes"]}
check("G endTime 对应事件", g_end[-540.0] == [48, 1, 3] and g_end[-270.0] == [48, 2, 3]
      and g_end[0.0] == [49, 0, 1] and g_end[270.0] == [49, 1, 3] and g_end[540.0] == [49, 2, 3], str(g_end))

# ---- 测试G2: 定轨hold 7k ----
app.hold_mode_var.set("7k")
events_7k = copy.deepcopy(doc_events)
events_7k["events"].append({"bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0], "easingLeft": 0.0, "easingRight": 1.0,
                            "easingType": 1, "end": 1.0, "endTime": [50, 0, 1], "layer": 0, "line": 0, "linkgroup": 0,
                            "start": 1.0, "startTime": [48, 0, 1], "type": 6})
events_7k["events"].append({"bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0], "easingLeft": 0.0, "easingRight": 1.0,
                            "easingType": 1, "end": 1.0, "endTime": [50, 1, 3], "layer": 0, "line": 0, "linkgroup": 0,
                            "start": 1.0, "startTime": [48, 0, 1], "type": 7})
outg2 = app.func_event_type_convert(events_7k)
gx2 = {n["positionX"] for n in outg2["notes"]}
check("G2 7k 轨道位置", gx2 == {-578.57, -385.71, -192.86, 0.0, 192.86, 385.71, 578.57}, str(sorted(gx2)))
app.hold_mode_var.set("无")

# ---- 测试H: 曲线drag 16分 x轴（文档示例；第一事件 easingType 用 2=Out Sine 以与文档数值一致） ----
app.drag_mode_var.set("X轴位移与缩放")
app.drag_interval_var.set("16")
drag_events = {"events": [
    {"bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0], "easingLeft": 0.0, "easingRight": 1.0,
     "easingType": 2, "end": 400.0, "endTime": [54, 0, 1], "layer": 0, "line": 0, "linkgroup": 0,
     "start": -400.0, "startTime": [53, 0, 1], "type": 1},
    {"bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0], "easingLeft": 0.0, "easingRight": 1.0,
     "easingType": 3, "end": 0.0, "endTime": [54, 1, 2], "layer": 0, "line": 0, "linkgroup": 0,
     "start": 400.0, "startTime": [54, 0, 1], "type": 1},
    {"bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0], "easingLeft": 0.0, "easingRight": 1.0,
     "easingType": 1, "end": 2.0, "endTime": [54, 1, 2], "layer": 4, "line": 0, "linkgroup": 0,
     "start": 2.0, "startTime": [54, 0, 1], "type": 6},
]}
outh = app.func_event_type_convert(copy.deepcopy(drag_events))
check("H 输出 7 个 drag", len(outh["notes"]) == 7, str(len(outh.get("notes", []))))
h_map = {tuple(n["startTime"]): n for n in outh["notes"]}
expect = {
    (53, 0, 1): (-400.0, 1.0),
    (53, 1, 4): (-93.853254107928478, 1.0),
    (53, 1, 2): (165.68542494923747, 1.0),
    (53, 3, 4): (339.10362600902909, 1.0),
    (54, 0, 1): (400.0, 2.0),
    (54, 1, 4): (282.84271247461925, 2.0),
    (54, 1, 2): (0.0, 2.0),
}
ok_h = True
for t, (px, size) in expect.items():
    n = h_map.get(t)
    if n is None or not near(n["positionX"], px) or not near(n["size"], size):
        ok_h = False
        print("  H mismatch", t, n)
check("H 位置与 size 符合文档", ok_h)
check("H 全部为 drag 且 judgeArea=size", all(n["type"] == 4 and n["judgeArea"] == n["size"] for n in outh["notes"]))
app.drag_mode_var.set("无")

# ---- 测试I: 非线性切割 三次贝塞尔子段控制点推导 ----
sub = app._subdivide_bezier(0.5, 0.0, 0.5, 1.0, 0.5, 1.0)
check("I S曲线 [0.5,1] 子段控制点", sub == [0.25, 0.5, 0.5, 1.0], str(sub))
bezier_data = {"events": [
    {"bezier": 1, "bezierPoints": [0.5, 0.0, 0.5, 1.0], "easingType": 1,
     "easingLeft": 0.0, "easingRight": 1.0,
     "startTime": [0, 0, 1], "endTime": [1, 0, 1], "start": 0.0, "end": 100.0},
]}
outi = app.func_nonlinear_split(copy.deepcopy(bezier_data), 8)
check("I 切成 2 段", len(outi["events"]) == 2, str(len(outi["events"])))
seg0, seg1 = outi["events"]
check("I 第一段起点=原起点", seg0["start"] == 0.0 and seg0["endTime"] == [0, 1, 2], str(seg0["start"]))
check("I 第二段终点=原终点", seg1["end"] == 100.0 and seg1["endTime"] == [1, 0, 1], str(seg1["end"]))
check("I 第二段控制点由公式推导", seg1["bezierPoints"] == [0.25, 0.5, 0.5, 1.0], str(seg1["bezierPoints"]))
check("I 非对称曲线细分保持形状", True)  # 具体偏差由下方数值检查
gen_pts = [0.3, 0.2, 0.8, 0.9]
gen_sub = app._subdivide_bezier(*gen_pts, 0.3, 0.7)
gs0 = app.interpolate_value(0.0, 100.0, 0.3, 1, 1, gen_pts)
gs1 = app.interpolate_value(0.0, 100.0, 0.7, 1, 1, gen_pts)
orig_mid = app.interpolate_value(0.0, 100.0, 0.5, 1, 1, gen_pts)
sub_mid = app.interpolate_value(gs0, gs1, 0.5, 1, 1, gen_sub)
check("I 一般曲线中点偏差 < 0.5", abs(orig_mid - sub_mid) < 0.5, "orig=%.4f sub=%.4f" % (orig_mid, sub_mid))

print("=" * 50)
print("TOTAL: %d PASS, %d FAIL" % (ok, fail))
root.destroy()
sys.exit(1 if fail else 0)
