# -*- coding: utf-8 -*-
"""RPET 改动功能测试（模块化版）"""
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


# ============ 测试1: 倒序拉伸 events 负值适配 ============
app.stretch_ratio_var.set("-1")
events = {"events": [
    {"type": 1, "line": 0, "layer": 0, "linkgroup": 0, "bezier": 1,
     "bezierPoints": [0.0, 0.0, 1.0, 1.0], "easingType": 2,
     "easingLeft": 0.0, "easingRight": 1.0,
     "startTime": [1, 0, 1], "endTime": [2, 0, 1], "start": 100.0, "end": 200.0},
    {"type": 1, "line": 0, "layer": 0, "linkgroup": 0, "bezier": 0,
     "bezierPoints": [0.0, 0.0, 0.0, 0.0], "easingType": 4,
     "easingLeft": 0.2, "easingRight": 0.8,
     "startTime": [3, 0, 1], "endTime": [4, 0, 1], "start": 0.0, "end": 50.0},
]}
out = app.func_reverse_data(copy.deepcopy(events))
ev0 = out["events"][0]
check("T1 时间交换(0->1, 1->0)", ev0["startTime"] == [0, 0, 1] and ev0["endTime"] == [1, 0, 1], str(ev0["startTime"]) + str(ev0["endTime"]))
check("T1 值交换", ev0["start"] == 200.0 and ev0["end"] == 100.0)
check("T1 in/out缓动交换(2->3)", ev0["easingType"] == 3, str(ev0["easingType"]))
check("T1 缓动左右(0,1)保持", abs(ev0["easingLeft"] - 0.0) < 1e-9 and abs(ev0["easingRight"] - 1.0) < 1e-9, str(ev0["easingLeft"]) + "," + str(ev0["easingRight"]))
check("T1 贝塞尔适配", ev0["bezierPoints"] == [0.0, 0.0, 1.0, 1.0], str(ev0["bezierPoints"]))
ev1 = out["events"][1]
check("T1 第二事件缓动(4->5)", ev1["easingType"] == 5, str(ev1["easingType"]))
check("T1 第二事件缓动左右 0.2,0.8 -> 0.2,0.8", abs(ev1["easingLeft"] - 0.2) < 1e-9 and abs(ev1["easingRight"] - 0.8) < 1e-9, str(ev1["easingLeft"]) + "," + str(ev1["easingRight"]))

# ============ 测试2: 倒序拉伸 notes 负值 hold 时间交换与 yOffset 翻转 ============
notes = {"notes": [
    {"type": 2, "startTime": [1, 0, 1], "endTime": [3, 0, 1], "positionX": 0.0, "yOffset": 10.0},
    {"type": 1, "startTime": [2, 0, 1], "endTime": [2, 0, 1], "positionX": 100.0},
]}
out2 = app.func_reverse_data(copy.deepcopy(notes))
n0 = out2["notes"][0]
check("T2 hold 时间交换", n0["startTime"] == [-1, 0, 1] and n0["endTime"] == [1, 0, 1], str(n0["startTime"]) + str(n0["endTime"]))
check("T2 yOffset 翻转", n0["yOffset"] == -10.0, str(n0["yOffset"]))
check("T2 tap 缩放后(0,0)", out2["notes"][1]["startTime"] == [0, 0, 1] and out2["notes"][1]["endTime"] == [0, 0, 1], str(out2["notes"][1]["startTime"]) + str(out2["notes"][1]["endTime"]))

# ============ 测试3: 图片转音符 x 坐标分布 ============
if Image is not None:
    img_path = os.path.join(BASE, "tests", "images", "_test_img.png")
    img = Image.new("RGB", (3, 3))
    px = img.load()
    colors = [(255, 255, 255), (0, 255, 255), (200, 200, 200),
              (100, 100, 100), (0, 255, 0), (0, 0, 255),
              (255, 0, 0), (240, 237, 105), (0, 0, 0)]
    for idx, c in enumerate(colors):
        px[idx % 3, idx // 3] = c
    img.save(img_path)
    app.image_path_var.set(img_path)
    app.use_original_size_var.set(True)
    app.auto_adjust_width_var.set(False)
    app.note_width_var.set("175")
    app.legacy_tint_var.set(False)
    out3 = app.func_image_to_notes({"imagePath": img_path})
    xs = [n["positionX"] for n in out3["notes"]]
    row0 = xs[0:3]
    check("T3 非自动宽度 x 分布", sorted(set(row0)) == sorted([-587.5, 0.0, 587.5]), str(row0))
    sizes = set(n["size"] for n in out3["notes"])
    check("T3 非自动宽度 175 -> size=1.0", sizes == {1.0}, str(sizes))
    app.note_width_var.set("350")
    out3w = app.func_image_to_notes({"imagePath": img_path})
    sizes_w = set(n["size"] for n in out3w["notes"])
    check("T3 非自动宽度 350 -> size=2.0", sizes_w == {2.0}, str(sizes_w))
    app.note_width_var.set("175")
    check("T3 默认 tint 键", all("tint" in n for n in out3["notes"]) and all("color" not in n for n in out3["notes"]))
    app.legacy_tint_var.set(True)
    out3b = app.func_image_to_notes({"imagePath": img_path})
    check("T3 旧版 color 键", all("color" in n for n in out3b["notes"]))
    app.legacy_tint_var.set(False)
    app.auto_adjust_width_var.set(True)
    out3c = app.func_image_to_notes({"imagePath": img_path})
    xs3c = sorted(set(n["positionX"] for n in out3c["notes"]))
    check("T3 自动宽度均匀分布", xs3c == sorted([-450.0, 0.0, 450.0]), str(xs3c))
    sizes3c = set(round(n["size"], 4) for n in out3c["notes"])
    check("T3 自动宽度 size=列间距/175", len(sizes3c) == 1 and abs(list(sizes3c)[0] - round(450.0 / 175.0, 4)) < 1e-6, str(sizes3c))
else:
    print("SKIP: 测试3 (Pillow 未安装)")

# ============ 测试4: hold 区分轨道 ============
app.distinguish_track_var.set(True)
data4 = {"notes": [
    {"type": 2, "startTime": [0, 0, 1], "endTime": [0, 0, 1], "positionX": 0.0},
    {"type": 2, "startTime": [1, 0, 1], "endTime": [1, 0, 1], "positionX": 100.0},
    {"type": 2, "startTime": [2, 0, 1], "endTime": [2, 0, 1], "positionX": 300.0},
    {"type": 2, "startTime": [3, 0, 1], "endTime": [3, 0, 1], "positionX": 310.0},
    {"type": 2, "startTime": [4, 0, 1], "endTime": [4, 0, 1], "positionX": 0.0},
]}
out4 = app.func_hold_notes_connect(copy.deepcopy(data4))
ends = {tuple(n["startTime"]): n["endTime"] for n in out4["notes"]}
check("T4 轨道区分 0->1", ends[tuple([0, 0, 1])] == [1, 0, 1], str(ends.get(tuple([0, 0, 1]))))
check("T4 轨道区分 1->4", ends[tuple([1, 0, 1])] == [4, 0, 1], str(ends.get(tuple([1, 0, 1]))))
check("T4 轨道区分 2->3", ends[tuple([2, 0, 1])] == [3, 0, 1], str(ends.get(tuple([2, 0, 1]))))
check("T4 轨道区分 最后一个保持", ends[tuple([4, 0, 1])] == [4, 0, 1], str(ends.get(tuple([4, 0, 1]))))

data4b = {"notes": [
    {"type": 2, "startTime": [0, 0, 1], "endTime": [0, 0, 1], "positionX": 0.0},
    {"type": 2, "startTime": [0, 0, 1], "endTime": [0, 0, 1], "positionX": 100.0},
    {"type": 2, "startTime": [2, 0, 1], "endTime": [2, 0, 1], "positionX": 50.0},
]}
out4b = app.func_hold_notes_connect(copy.deepcopy(data4b))
endsb = [n["endTime"] for n in out4b["notes"]]
check("T4 双押共同参考下一时间", endsb[0] == [2, 0, 1] and endsb[1] == [2, 0, 1] and endsb[2] == [2, 0, 1], str(endsb))

app.distinguish_track_var.set(False)
data4c = {"notes": [
    {"type": 2, "startTime": [0, 0, 1], "endTime": [0, 0, 1], "positionX": 0.0},
    {"type": 2, "startTime": [1, 0, 1], "endTime": [1, 0, 1], "positionX": 100.0},
    {"type": 2, "startTime": [2, 0, 1], "endTime": [2, 0, 1], "positionX": 300.0},
]}
out4c = app.func_hold_notes_connect(copy.deepcopy(data4c))
endsc = [n["endTime"] for n in out4c["notes"]]
check("T4 非区分模式 0->1, 1->2", endsc[0] == [1, 0, 1] and endsc[1] == [2, 0, 1] and endsc[2] == [2, 0, 1], str(endsc))

print("=" * 50)
print("TOTAL: %d PASS, %d FAIL" % (ok, fail))
root.destroy()
sys.exit(1 if fail else 0)
