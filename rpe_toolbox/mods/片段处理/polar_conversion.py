# -*- coding: utf-8 -*-
"""模组：极坐标转换

所属功能组：片段处理
MOD_KEY 与 assets/lang/*.json 里 functions[].key 对应；序号由主程序加载时决定，本文件不写序号。
"""

import copy
import math

from rpe_toolbox.i18n import t

from rpe_toolbox.shared import density_of, density_row

MOD_KEY = "polar_conversion"
MOD_ORDER = 30

def process(app, data, density=None):
    density = density_of(app, density)
    events = data.get("events", [])
    if not events:
        return data

    all_times = set()
    for e in events:
        all_times.add(app.time_to_float(e["startTime"]))
        all_times.add(app.time_to_float(e["endTime"]))

    if not all_times:
        return data

    min_t = min(all_times)
    max_t = max(all_times)

    # 按密度生成时间轴，并合并所有事件的边界时刻（跳变时刻必须被精确采样）
    step = 4.0 / density
    if step <= 0:
        step = 0.25

    grid_times = []
    current_t = min_t
    while current_t <= max_t + 1e-6:
        grid_times.append(current_t)
        current_t += step

    timeline = sorted(t for t in (set(grid_times) | all_times)
                      if min_t - 1e-9 <= t <= max_t + 1e-9)

    # 按 type 预分组，避免每次采样都重新过滤/排序
    events_by_type = {}
    for e in events:
        events_by_type.setdefault(e["type"], []).append(e)
    for type_evts in events_by_type.values():
        type_evts.sort(key=lambda x: app.time_to_float(x["startTime"]))

    def _event_value_at(active, t):
        """按 easingLeft/easingRight 窗口计算事件在时刻 t 的值，窗口外钳位到 start/end"""
        s = app.time_to_float(active["startTime"])
        en = app.time_to_float(active["endTime"])
        start_v = active["start"]
        end_v = active["end"]
        dur = en - s
        if dur < 1e-9:
            # 零时长事件视为瞬时跳变
            return end_v
        p = (t - s) / dur
        easing_left = active.get("easingLeft", 0.0)
        easing_right = active.get("easingRight", 1.0)
        if easing_right < easing_left:
            easing_left, easing_right = easing_right, easing_left
        if p <= easing_left:
            return start_v
        if p >= easing_right:
            return end_v
        span = easing_right - easing_left
        if span < 1e-9:
            return end_v
        norm = (p - easing_left) / span
        eased = app.apply_easing(norm, active.get("easingType", 1),
                                  active.get("bezier", 0),
                                  active.get("bezierPoints", [0.0, 0.0, 0.0, 0.0]))
        return start_v + (end_v - start_v) * eased

    def sample(t, target_type, side):
        """取某类型事件在时刻 t 的值；side='right' 取右极限（新开始的事件优先），
        side='left' 取左极限（旧事件优先）。未定义段沿用上个事件结束值，否则用下一个事件起始值。"""
        type_evts = events_by_type.get(target_type)
        if not type_evts:
            return 0.0

        best = None
        best_s = None
        for e in type_evts:
            s = app.time_to_float(e["startTime"])
            en = app.time_to_float(e["endTime"])
            started = s <= t + 1e-9 if side == "right" else s < t - 1e-9
            if started and en >= t - 1e-9:
                if best is None or s >= best_s:
                    best = e
                    best_s = s
        if best is not None:
            return _event_value_at(best, t)

        prev_val = None
        for e in type_evts:
            if app.time_to_float(e["endTime"]) < t - 1e-9:
                prev_val = e["end"]
            else:
                break
        if prev_val is not None:
            return prev_val

        for e in type_evts:
            if app.time_to_float(e["startTime"]) > t + 1e-9:
                return e["start"]

        return 0.0

    EPS = 1e-6
    temp_events_x = []
    temp_events_y = []
    last_x = None
    last_y = None

    def make_ev(ttype, t0, t1, v0, v1):
        return {
            "type": ttype, "line": 0, "layer": 0, "linkgroup": 0,
            "bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0],
            "easingType": 1, "easingLeft": 0.0, "easingRight": 1.0,
            "startTime": app.float_to_time(t0), "endTime": app.float_to_time(t1),
            "start": v0, "end": v1,
        }

    def emit(evt_list, v0, v1, last_val, ttype, t0, t1, force=False):
        """输出一个线性段；区间起点相对上一输出发生跳变时也必须输出以锚定新值"""
        changed = abs(v1 - v0) > EPS
        jumped = last_val is not None and abs(v0 - last_val) > EPS
        if not changed and not jumped and not force:
            return last_val
        evt_list.append(make_ev(ttype, t0, t1, v0, v1))
        return v1

    has_xy = 1 in events_by_type or 2 in events_by_type

    # 逐区间输出：区间起点取右极限（跳变后的新值），终点取左极限（跳变前的旧值），
    # 再各自做极坐标换算。输入事件在某时刻数值突变时，输出拆成
    # "上一段以旧值结束 + 下一段以新值开始" 两段，而不是用一段时间做平滑过渡。
    for i in range(len(timeline) - 1):
        t0 = timeline[i]
        t1 = timeline[i + 1]

        x0 = sample(t0, 1, "right"); x1 = sample(t1, 1, "left")
        y0 = sample(t0, 2, "right"); y1 = sample(t1, 2, "left")
        r0 = sample(t0, 3, "right"); r1 = sample(t1, 3, "left")

        d0 = math.sqrt(x0 ** 2 + y0 ** 2)
        d1 = math.sqrt(x1 ** 2 + y1 ** 2)
        v0x = d0 * math.sin(math.radians(r0)); v1x = d1 * math.sin(math.radians(r1))
        v0y = d0 * math.cos(math.radians(r0)); v1y = d1 * math.cos(math.radians(r1))

        # 首个区间强制输出一次，锚定各通道初始值，保证后续任何跳变都有明确的"前值"可对照
        last_x = emit(temp_events_x, v0x, v1x, last_x, 1, t0, t1, force=(i == 0 and has_xy))
        last_y = emit(temp_events_y, v0y, v1y, last_y, 2, t0, t1, force=(i == 0 and has_xy))

    # 旋转事件不切割：直接复制输入的旋转事件（旋转仍参与 r/θ 换算，只是输出保持输入原貌）
    copied_rotations = [copy.deepcopy(e) for e in events if e.get("type") == 3]

    new_events = temp_events_x + temp_events_y + copied_rotations
    data["events"] = new_events
    return data

def build_options(app, parent):
    """切割密度输入行（两个用到密度的功能共用 shared.density_row）。"""
    density_row(app, parent)
