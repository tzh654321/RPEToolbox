# -*- coding: utf-8 -*-
"""模组：非线性切割

所属功能组：片段处理
MOD_KEY 与 assets/lang/*.json 里 functions[].key 对应；序号由主程序加载时决定，本文件不写序号。
"""

import copy

from rpe_toolbox.shared import density_of, density_row

MOD_KEY = "nonlinear_split"
MOD_ORDER = 20

def process(app, data, density=None):
    density = density_of(app, density)
    events = data.get("events", [])
    new_events = []

    for event in events:
        # 获取起始和结束时间
        t_start = app.time_to_float(event["startTime"])
        t_end = app.time_to_float(event["endTime"])

        if t_start >= t_end:
            new_events.append(event)
            continue

        duration = t_end - t_start
        # 分音密度：16分音 = 1/4 拍，故 step = 4 / density（推导见 Other File/大段注释整理.md）
        step = 4.0 / density
        if step <= 0:
            step = 0.25  # fallback

        current_t = t_start
        easing_type = event.get("easingType", 1)
        easing_left = event.get("easingLeft", 0.0)
        easing_right = event.get("easingRight", 1.0)
        bezier_flag = event.get("bezier", 0)
        bezier_points = event.get("bezierPoints", [0.0, 0.0, 0.0, 0.0])

        while current_t < t_end - 1e-6:
            next_t = min(current_t + step, t_end)

            # 在原事件时长内计算每段的进度，并映射到缓动坐标
            seg_progress_start = (current_t - t_start) / duration
            seg_progress_end = (next_t - t_start) / duration

            cur_ease_l = easing_left + (easing_right - easing_left) * seg_progress_start
            cur_ease_r = easing_left + (easing_right - easing_left) * seg_progress_end

            # 按缓动类型或贝塞尔曲线计算段首尾值
            val_start = app.interpolate_value(event["start"], event["end"], seg_progress_start, easing_type, bezier_flag, bezier_points)
            val_end = app.interpolate_value(event["start"], event["end"], seg_progress_end, easing_type, bezier_flag, bezier_points)

            new_ev = copy.deepcopy(event)
            new_ev["startTime"] = app.float_to_time(current_t)
            new_ev["endTime"] = app.float_to_time(next_t)
            new_ev["start"] = val_start
            new_ev["end"] = val_end
            new_ev["easingLeft"] = cur_ease_l
            new_ev["easingRight"] = cur_ease_r
            # 需求十一：三次贝塞尔改为按数学公式（de Casteljau 细分）推导每一小段的控制点
            if bezier_flag == 1 and isinstance(bezier_points, list) and len(bezier_points) == 4:
                sub_points = app._subdivide_bezier(
                    bezier_points[0], bezier_points[1],
                    bezier_points[2], bezier_points[3],
                    seg_progress_start, seg_progress_end,
                )
                if sub_points is not None:
                    new_ev["bezierPoints"] = sub_points
            # 保留原 easingType（与需求示例输出一致）
            new_events.append(new_ev)
            current_t = next_t

    data["events"] = new_events
    return data

def build_options(app, parent):
    """切割密度输入行（两个用到密度的功能共用 shared.density_row）。"""
    density_row(app, parent)
