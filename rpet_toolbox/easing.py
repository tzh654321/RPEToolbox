# -*- coding: utf-8 -*-
"""时间数组与缓动曲线数学（原 RPET.py 中 time_to_float ~ interpolate_value）。

原实现中的大段说明性注释已移至 Other File/大段注释整理.md。
"""

import math


class EasingMixin:
    # 辅助函数：时间数组处理 [beat, numerator, denominator] -> float beats
    def time_to_float(self, t_arr):
        if isinstance(t_arr, list) and len(t_arr) == 3:
            return t_arr[0] + t_arr[1] / t_arr[2]
        return float(t_arr)

    def float_to_time(self, val):
        # 输出 [a, b, c] 格式：整数拍 + 分母 <= 192 的最简分数表示
        beat = int(val)
        remainder = val - beat
        if abs(remainder) < 1e-6:
            return [beat, 0, 1]

        best_b, best_c = 1, 1
        min_diff = 1.0
        for c in range(1, 193):
            b = round(remainder * c)
            diff = abs(b / c - remainder)
            if diff < min_diff:
                min_diff = diff
                best_b, best_c = b, c
                if diff < 1e-6:
                    break

        return [beat, best_b, best_c]

    def cubic_bezier(self, t, x1, y1, x2, y2):
        # 输入 t 为时间进度，返回贝塞尔曲线上的 y（x->t 牛顿法反解）
        def sample_curve_x(t_):
            return ((3 * x1 - 3 * x2 + 1) * t_ ** 3 + (-6 * x1 + 3 * x2) * t_ ** 2 + (3 * x1) * t_)

        def sample_curve_y(t_):
            return ((3 * y1 - 3 * y2 + 1) * t_ ** 3 + (-6 * y1 + 3 * y2) * t_ ** 2 + (3 * y1) * t_)

        def sample_curve_derivative_x(t_):
            return (3 * (3 * x1 - 3 * x2 + 1) * t_ ** 2 + 2 * (-6 * x1 + 3 * x2) * t_ + 3 * x1)

        t_hat = t
        for _ in range(8):
            x_est = sample_curve_x(t_hat) - t
            dx = sample_curve_derivative_x(t_hat)
            if abs(dx) < 1e-6:
                break
            t_hat -= x_est / dx
            t_hat = max(0.0, min(1.0, t_hat))
        return sample_curve_y(t_hat)

    def apply_easing(self, t, easing_type, bezier, bezier_points):
        if t <= 0:
            return 0.0
        if t >= 1:
            return 1.0

        if bezier == 1 and isinstance(bezier_points, list) and len(bezier_points) == 4:
            x1, y1, x2, y2 = bezier_points
            return self.cubic_bezier(t, x1, y1, x2, y2)

        # 用户指定的 easingType 对应关系
        if easing_type == 1:
            return t
        if easing_type == 2:
            return math.sin((t * math.pi) / 2)
        if easing_type == 3:
            return 1 - math.cos((t * math.pi) / 2)
        if easing_type == 4:
            return 1 - (1 - t) * (1 - t)
        if easing_type == 5:
            return t ** 2
        if easing_type == 6:
            return -(math.cos(math.pi * t) - 1) / 2
        if easing_type == 7:
            return 2 * (t ** 2) if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2
        if easing_type == 8:
            return 1 - (1 - t) ** 3
        if easing_type == 9:
            return t ** 3
        if easing_type == 10:
            return 1 - (1 - t) ** 4
        if easing_type == 11:
            return t ** 4
        if easing_type == 12:
            return 4 * (t ** 3) if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2
        if easing_type == 13:
            return 8 * (t ** 4) if t < 0.5 else 1 - (-2 * t + 2) ** 4 / 2
        if easing_type == 14:
            return 1 - (1 - t) ** 5
        if easing_type == 15:
            return t ** 5
        if easing_type == 16:
            return 1 if t == 1 else 1 - 2 ** (-10 * t)
        if easing_type == 17:
            return 0 if t == 0 else 2 ** (10 * t - 10)
        if easing_type == 18:
            return math.sqrt(1 - (t - 1) ** 2)
        if easing_type == 19:
            return 1 - math.sqrt(1 - t * t)
        if easing_type == 20:
            c1 = 1.70158
            c3 = c1 + 1
            return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2
        if easing_type == 21:
            c1 = 1.70158
            c3 = c1 + 1
            return c3 * t ** 3 - c1 * t ** 2
        if easing_type == 22:
            return (1 - math.sqrt(1 - (2 * t) ** 2)) / 2 if t < 0.5 else (math.sqrt(1 - (-2 * t + 2) ** 2) + 1) / 2
        if easing_type == 23:
            c2 = 2.5949095
            if t < 0.5:
                return ((2 * t) ** 2 * ((c2 + 1) * 2 * t - c2)) / 2
            return ((2 * t - 2) ** 2 * ((c2 + 1) * (2 * t - 2) + c2) + 2) / 2
        if easing_type == 24:
            if t == 0:
                return 0
            if t == 1:
                return 1
            return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi / 3)) + 1
        if easing_type == 25:
            if t == 0:
                return 0
            if t == 1:
                return 1
            return -2 ** (10 * t - 10) * math.sin((t * 10 - 10.75) * (2 * math.pi / 3))
        if easing_type == 26:
            if t < 1 / 2.75:
                return 7.5625 * t * t
            if t < 2 / 2.75:
                t -= 1.5 / 2.75
                return 7.5625 * t * t + 0.75
            if t < 2.5 / 2.75:
                t -= 2.25 / 2.75
                return 7.5625 * t * t + 0.9375
            t -= 2.625 / 2.75
            return 7.5625 * t * t + 0.984375
        if easing_type == 27:
            return 1 - self.apply_easing(1 - t, 26, 0, [0.0, 0.0, 0.0, 0.0])
        if easing_type == 28:
            if t < 0.5:
                return (1 - self.apply_easing(1 - 2 * t, 26, 0, [0.0, 0.0, 0.0, 0.0])) / 2
            return (1 + self.apply_easing(2 * t - 1, 26, 0, [0.0, 0.0, 0.0, 0.0])) / 2
        if easing_type == 29:
            if t == 0:
                return 0
            if t == 1:
                return 1
            if t < 0.5:
                return - (2 ** (20 * t - 10)) * math.sin((20 * t - 11.125) * ((2 * math.pi) / 4.5)) / 2
            return (2 ** (-20 * t + 10)) * math.sin((20 * t - 11.125) * ((2 * math.pi) / 4.5)) / 2 + 1
        return t

    def interpolate_value(self, start, end, progress, easing_type, bezier, bezier_points):
        eased = self.apply_easing(progress, easing_type, bezier, bezier_points)
        return start + (end - start) * eased
