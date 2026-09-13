# -*- coding: utf-8 -*-
"""功能1 "是否允许长度缩短" 验证：默认开启=原行为；关闭后被缩短的长条/事件改为延长"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import tkinter as tk

from rpe_toolbox.app import RPEToolbox

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


def hold(t0, t1, x=0.0):
    return {"type": 2, "positionX": x, "startTime": t0, "endTime": t1, "line": 0}


def ev(t0, t1, line=0):
    return {"type": 1, "line": line, "startTime": t0, "endTime": t1, "start": 0.0, "end": 0.0}


def flt(t):
    return app.time_to_float(t)


def ends(items):
    return [flt(i["endTime"]) for i in items]


# E. UI: 默认勾选（必须在修改变量之前检查）
check("E1 默认勾选允许缩短", app.allow_shorten_var.get() is True)


# ---------- A. 不区分轨道 notes ----------
app.distinguish_track_var.set(False)

# A1 默认开启：原行为（长条被缩短到下一个开始时间）
app.allow_shorten_var.set(True)
data = {"notes": [hold([0, 0, 1], [4, 0, 1]), hold([2, 0, 1], [3, 0, 1])]}
out = app.func_hold_connect(data)
check("A1 开启-长条缩短到2", ends(out["notes"]) == [2.0, 3.0], str(ends(out["notes"])))

# A2 关闭：本会被缩短的长条保持原样（之后无开始时间）
app.allow_shorten_var.set(False)
data = {"notes": [hold([0, 0, 1], [4, 0, 1]), hold([2, 0, 1], [3, 0, 1])]}
out = app.func_hold_connect(data)
check("A2 关闭-无后续则保持4", ends(out["notes"]) == [4.0, 3.0], str(ends(out["notes"])))

# A3 关闭：从结束时间起延长到下一个开始时间
app.allow_shorten_var.set(False)
data = {"notes": [hold([0, 0, 1], [4, 0, 1]), hold([2, 0, 1], [3, 0, 1]), hold([5, 0, 1], [6, 0, 1])]}
out = app.func_hold_connect(data)
check("A3 关闭-延长到5", ends(out["notes"]) == [5.0, 5.0, 6.0], str(ends(out["notes"])))

# A4 关闭：需要延长的长条行为不变
app.allow_shorten_var.set(False)
data = {"notes": [hold([0, 0, 1], [1, 0, 1]), hold([2, 0, 1], [3, 0, 1])]}
out = app.func_hold_connect(data)
check("A4 关闭-延长行为不变", ends(out["notes"]) == [2.0, 3.0], str(ends(out["notes"])))

# A5 关闭：已首尾相接的长条不再继续延长
app.allow_shorten_var.set(False)
data = {"notes": [hold([0, 0, 1], [2, 0, 1]), hold([2, 0, 1], [3, 0, 1]), hold([4, 0, 1], [5, 0, 1])]}
out = app.func_hold_connect(data)
check("A5 关闭-已相接不延长", ends(out["notes"]) == [2.0, 4.0, 5.0], str(ends(out["notes"])))

# ---------- B. 不区分轨道 events ----------
app.distinguish_track_var.set(False)

app.allow_shorten_var.set(True)
data = {"events": [ev([0, 0, 1], [4, 0, 1]), ev([2, 0, 1], [3, 0, 1])]}
out = app.func_hold_connect(data)
check("B1 事件开启-缩短到2", ends(out["events"]) == [2.0, 3.0], str(ends(out["events"])))

app.allow_shorten_var.set(False)
data = {"events": [ev([0, 0, 1], [4, 0, 1]), ev([2, 0, 1], [3, 0, 1]), ev([5, 0, 1], [6, 0, 1])]}
out = app.func_hold_connect(data)
check("B2 事件关闭-延长到5", ends(out["events"]) == [5.0, 5.0, 6.0], str(ends(out["events"])))

# ---------- C. 区分轨道 notes（x 差距 < 175 分组）----------
app.distinguish_track_var.set(True)

# C1 关闭：本轨道内被缩短的 hold 延长到结束时间之后的下一个同轨开始时间
app.allow_shorten_var.set(False)
data = {"notes": [hold([0, 0, 1], [4, 0, 1], x=0), hold([2, 0, 1], [3, 0, 1], x=0), hold([5, 0, 1], [6, 0, 1], x=0)]}
out = app.func_hold_connect(data)
check("C1 区分轨道关闭-延长到5", ends(out["notes"]) == [5.0, 5.0, 6.0], str(ends(out["notes"])))

# C2 关闭：结束时间之后无同轨 hold 则保持原样
app.allow_shorten_var.set(False)
data = {"notes": [hold([0, 0, 1], [4, 0, 1], x=0), hold([2, 0, 1], [3, 0, 1], x=0)]}
out = app.func_hold_connect(data)
check("C2 区分轨道关闭-保持4", ends(out["notes"]) == [4.0, 3.0], str(ends(out["notes"])))

# C3 开启：默认行为与原逻辑一致（缩短到下一个开始时间）
app.allow_shorten_var.set(True)
data = {"notes": [hold([0, 0, 1], [4, 0, 1], x=0), hold([2, 0, 1], [3, 0, 1], x=0), hold([5, 0, 1], [6, 0, 1], x=0)]}
out = app.func_hold_connect(data)
check("C3 区分轨道开启-缩短到2", ends(out["notes"]) == [2.0, 5.0, 6.0], str(ends(out["notes"])))

# C4 关闭：另一轨道（x 差 >= 175）的开始时间不参与延长
app.allow_shorten_var.set(False)
data = {"notes": [hold([0, 0, 1], [4, 0, 1], x=0), hold([2, 0, 1], [3, 0, 1], x=500), hold([5, 0, 1], [6, 0, 1], x=0)]}
out = app.func_hold_connect(data)
check("C4 区分轨道关闭-跨轨不干扰", ends(out["notes"]) == [5.0, 3.0, 6.0], str(ends(out["notes"])))

# ---------- D. 区分轨道 events（按 line 分组）----------
app.distinguish_track_var.set(True)

app.allow_shorten_var.set(True)
data = {"events": [ev([0, 0, 1], [4, 0, 1], line=0), ev([2, 0, 1], [3, 0, 1], line=0), ev([5, 0, 1], [6, 0, 1], line=1)]}
out = app.func_hold_connect(data)
# ev1 缩短到 2；ev2 所在 line0 组在 2 之后无其他开始时间 → 保持 3；ev3 单独 line1 → 保持 6
check("D1 事件开启-仅同line缩短", ends(out["events"]) == [2.0, 3.0, 6.0], str(ends(out["events"])))

app.allow_shorten_var.set(False)
data = {"events": [ev([0, 0, 1], [4, 0, 1], line=0), ev([2, 0, 1], [3, 0, 1], line=0), ev([5, 0, 1], [6, 0, 1], line=0)]}
out = app.func_hold_connect(data)
check("D2 事件关闭-同line延长到5", ends(out["events"]) == [5.0, 5.0, 6.0], str(ends(out["events"])))

print("=" * 50)
print("TOTAL: %d PASS, %d FAIL" % (ok, fail))
root.destroy()
raise SystemExit(0 if fail == 0 else 1)
