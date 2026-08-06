# -*- coding: utf-8 -*-
"""需求九修复验证（模块化版）"""
import os
import struct
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import tkinter as tk

from rpet_toolbox.app import RPEToolbox
from rpet_toolbox.imglib import Image

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


# ---- 测试A: BPMList 格式 ----
def make_midi(path):
    header = b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big") + (1).to_bytes(2, "big") + (480).to_bytes(2, "big")
    tempo = 500000  # 120 BPM
    track_data = bytes([0x00, 0xFF, 0x51, 0x03]) + tempo.to_bytes(3, "big") + bytes([0x00, 0xFF, 0x2F, 0x00])
    track = b"MTrk" + len(track_data).to_bytes(4, "big") + track_data
    with open(path, "wb") as f:
        f.write(header + track)


midi_path = os.path.join(BASE, "tests", "_test_req9.mid")
make_midi(midi_path)
app.midi_path_var.set(midi_path)
out = app.func_extract_midi_bpm({})
check("A BPMList 键存在且无 midiPath", "BPMList" in out and "midiPath" not in out and "bpmChanges" not in out, str(list(out.keys())))
check("A BPM 值 120", abs(out["BPMList"][0]["bpm"] - 120.0) < 0.01, str(out["BPMList"]))
check("A startTime [0,0,1]", out["BPMList"][0]["startTime"] == [0, 0, 1], str(out["BPMList"][0]["startTime"]))

# ---- 测试B: 自动调整音符宽度 -> size ----
img_path = os.path.join(BASE, "assets", "images", "_test_img3x3.png")
img = Image.new("RGB", (3, 3))
px = img.load()
for idx, c in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255),
                         (255, 255, 255), (0, 0, 0), (200, 200, 200),
                         (100, 100, 100), (0, 255, 255), (240, 237, 105)]):
    px[idx % 3, idx // 3] = c
img.save(img_path)
app.image_path_var.set(img_path)
app.use_original_size_var.set(True)
app.auto_adjust_width_var.set(True)
app.legacy_tint_var.set(False)
outb = app.func_image_to_notes({"imagePath": img_path})
sizes = set(round(n["size"], 4) for n in outb["notes"])
check("B 自动宽度 size=step/175", len(sizes) == 1 and abs(list(sizes)[0] - (1350 / 3) / 175) < 0.01, str(sizes))
app.auto_adjust_width_var.set(False)
app.note_width_var.set("175")
outb2 = app.func_image_to_notes({"imagePath": img_path})
sizes2 = set(n["size"] for n in outb2["notes"])
check("B 非自动宽度 175 size=1.0", sizes2 == {1.0}, str(sizes2))
app.note_width_var.set("350")
outb3 = app.func_image_to_notes({"imagePath": img_path})
sizes3 = set(n["size"] for n in outb3["notes"])
check("B 非自动宽度 350 size=2.0", sizes3 == {2.0}, str(sizes3))
app.note_width_var.set("175")

# ---- 测试C: 上下翻转反义（默认未勾选 -> 底部行最早） ----
app.auto_adjust_width_var.set(True)
app.flip_vertical_var.set(False)
outc = app.func_image_to_notes({"imagePath": img_path})
# 图行序: row0=(255,0,0),(0,255,0),(0,0,255); row1=white,black,gray; row2=(100,100,100),cyan,240
# 默认未勾选 -> 翻转后生成 -> 第一行为原底部行(row2)，左下角=(100,100,100)
first_note = outc["notes"][0]
check("C 默认(未勾选)底部行最早", first_note["tint"] == [100, 100, 100], str(first_note["tint"]))
# 勾选上下翻转 -> 不翻转 -> 第一行为原顶部行(row0)，左上角=(255,0,0)
app.flip_vertical_var.set(True)
outc2 = app.func_image_to_notes({"imagePath": img_path})
first2 = outc2["notes"][0]
check("C 勾选后不翻转(顶部行最早)", first2["tint"] == [255, 0, 0], str(first2["tint"]))
app.flip_vertical_var.set(False)

# ---- 测试D: 多透明度测试图片 ----
alpha_path = os.path.join(BASE, "assets", "images", "_test_img_alpha.png")
with Image.open(alpha_path) as alpha_img:
    alphas = sorted({p[3] for p in alpha_img.convert("RGBA").getdata()})
check("D 透明度包含 0/127/255", {0, 127, 255}.issubset(set(alphas)), str(alphas))

print("=" * 50)
print("TOTAL: %d PASS, %d FAIL" % (ok, fail))
root.destroy()
sys.exit(1 if fail else 0)
