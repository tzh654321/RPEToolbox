# -*- coding: utf-8 -*-
"""RPEToolbox 新版 func_polar_conversion 修复验证: easingLeft/Right 兼容 + 数值突变保真"""
import os
import sys

BASE = r"C:\Users\tzh\Documents\code\RPEToolbox"
sys.path.insert(0, BASE)

from rpe_toolbox.core import FunctionMixin

app = object.__new__(FunctionMixin)


def mk(start_t, end_t, s, e, typ, **kw):
    d = {"type": typ, "line": 1, "layer": 0, "linkgroup": 0, "bezier": 0,
         "bezierPoints": [0.0, 0.0, 0.0, 0.0], "easingType": 1,
         "easingLeft": 0.0, "easingRight": 1.0,
         "startTime": start_t, "endTime": end_t, "start": s, "end": e}
    d.update(kw)
    return d


def run(events, density=4):
    data = {"events": [dict(x) for x in events]}
    return app.func_polar_conversion(data, density)


def flt(t):
    return app.time_to_float(t)


ok = True
def check(name, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + name + (" | " + detail if detail else ""))
    if not cond:
        ok = False


# ---------- 测试 1: easingLeft/easingRight 兼容 ----------
# X: 0->100, beat 0..4, 线性, easingLeft=0.25, easingRight=0.75; rot 恒 90 => new_x = dist = |x|
out = run([mk([0, 0, 1], [4, 0, 1], 0.0, 100.0, 1, easingLeft=0.25, easingRight=0.75),
           mk([0, 0, 1], [4, 0, 1], 90.0, 90.0, 3)])
x_evs = sorted([e for e in out["events"] if e["type"] == 1 and abs(e["end"] - e["start"]) > 1e-6],
               key=lambda e: flt(e["startTime"]))
print("test1 x events:", [(flt(e["startTime"]), flt(e["endTime"]), e["start"], e["end"]) for e in x_evs])
check("easing窗口-变化段数", len(x_evs) == 2, "got %d" % len(x_evs))
if len(x_evs) == 2:
    e0, e1 = x_evs
    check("easing窗口-第一段", abs(flt(e0["startTime"]) - 1) < 1e-6 and abs(flt(e0["endTime"]) - 2) < 1e-6
          and abs(e0["start"]) < 1e-6 and abs(e0["end"] - 50) < 1e-6,
          "(%.3f,%.3f) %.2f->%.2f" % (flt(e0["startTime"]), flt(e0["endTime"]), e0["start"], e0["end"]))
    check("easing窗口-第二段", abs(flt(e1["startTime"]) - 2) < 1e-6 and abs(flt(e1["endTime"]) - 3) < 1e-6
          and abs(e1["start"] - 50) < 1e-6 and abs(e1["end"] - 100) < 1e-6,
          "(%.3f,%.3f) %.2f->%.2f" % (flt(e1["startTime"]), flt(e1["endTime"]), e1["start"], e1["end"]))
check("easing窗口-钳位起点", all(flt(e["startTime"]) >= 1 - 1e-6 for e in x_evs))

# ---------- 测试 2: 数值突变保真 ----------
# X: [0,2] 0->0; [2,4] 100->100, rot 恒 90 => new_x = dist = |x|
out2 = run([mk([0, 0, 1], [2, 0, 1], 0.0, 0.0, 1),
            mk([2, 0, 1], [4, 0, 1], 100.0, 100.0, 1),
            mk([0, 0, 1], [4, 0, 1], 90.0, 90.0, 3)])
x2 = sorted([e for e in out2["events"] if e["type"] == 1], key=lambda e: flt(e["startTime"]))
print("test2 x events:", [(flt(e["startTime"]), flt(e["endTime"]), e["start"], e["end"]) for e in x2])
starts_at_2 = any(abs(flt(e["startTime"]) - 2) < 1e-6 and abs(e["start"] - 100) < 1e-6 for e in x2)
no_ramp = all(not (abs(e["end"] - e["start"]) > 50 and min(abs(e["start"]), abs(e["end"])) < 1
                   and max(abs(e["start"]), abs(e["end"])) > 99) for e in x2)
prev_anchored = any(abs(e["end"]) < 1e-6 and flt(e["endTime"]) <= 2 + 1e-6 for e in x2)
check("突变-t=2处直接以新值开始", starts_at_2)
check("突变-无平滑坡道", no_ramp)
check("突变-旧值有输出锚定", prev_anchored)

# ---------- 测试 3: 缓动窗口 + 突变组合 ----------
out3 = run([mk([0, 0, 1], [2, 0, 1], 0.0, 100.0, 1, easingLeft=0.5, easingRight=1.0),
            mk([2, 0, 1], [4, 0, 1], 0.0, 0.0, 1),
            mk([0, 0, 1], [4, 0, 1], 90.0, 90.0, 3)])
x3 = sorted([e for e in out3["events"] if e["type"] == 1], key=lambda e: flt(e["startTime"]))
print("test3 x events:", [(flt(e["startTime"]), flt(e["endTime"]), e["start"], e["end"]) for e in x3])
has_ramp = any(abs(flt(e["startTime"]) - 1) < 1e-6 and abs(flt(e["endTime"]) - 2) < 1e-6
               and abs(e["start"]) < 1e-6 and abs(e["end"] - 100) < 1e-6 for e in x3)
anchor_after = any(abs(flt(e["startTime"]) - 2) < 1e-6 and abs(e["start"]) < 1e-6 and abs(e["end"]) < 1e-6 for e in x3)
check("窗口+突变-斜坡段从t=1开始", has_ramp)
check("窗口+突变-t=2处锚定回0", anchor_after)

print("\nALL %s" % ("PASSED" if ok else "FAILED"))
raise SystemExit(0 if ok else 1)
